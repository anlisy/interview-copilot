from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Mapping

from .metrics import aggregate
from .policy import apply_threshold_policy
from ..decision.calibration import ThresholdPolicy
from ..decision.base import DecisionEngine
from ..decision.schema import DecisionTask


def load_jsonl(path: str | Path) -> list[dict]:
    rows = []
    for lineno, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid benchmark JSONL {path}:{lineno}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"benchmark row {lineno} must be object")
        for key in ("id", "task_type", "state", "options", "expected"):
            if key not in row:
                raise ValueError(f"benchmark row {lineno} missing {key}")
        if row["task_type"] not in {"skill", "tool", "intent"}:
            raise ValueError(f"row {row['id']} has unsupported task_type")
        rows.append(row)
    return rows


def _build_task(case: dict, expected_choice: str | None = None) -> DecisionTask:
    options = {str(k): str(v) for k, v in case["options"].items()}
    return DecisionTask(
        task_id=str(case["id"]),
        task_type=str(case["task_type"]),
        state=case["state"],
        options=options,
        metadata={"expected_choice": expected_choice or case["expected"], **case.get("metadata", {})},
    )


def run_engine(
    engine: DecisionEngine,
    cases: Iterable[dict],
    *,
    fallback_engine: DecisionEngine | None = None,
    fallback_cache: dict[tuple[str, str], dict] | None = None,
    policy: ThresholdPolicy | None = None,
    precompute_fallback: bool = False,
) -> list[dict]:
    out = []
    fallback_cache = fallback_cache if fallback_cache is not None else {}
    for case in cases:
        task = _build_task(case)
        result = engine.decide(task)
        active_policy = policy or ThresholdPolicy()
        route = active_policy.route(result.confidence)
        effective_choice = result.choice
        fallback_record = None
        fallback_applied = False
        should_compute_fallback = precompute_fallback or route == "fallback"
        if should_compute_fallback and fallback_engine is not None and fallback_engine.name != engine.name:
            cache_key = (fallback_engine.name, task.task_id)
            fallback_record = fallback_cache.get(cache_key)
            if fallback_record is None:
                fb_result = fallback_engine.decide(task)
                fallback_record = {
                    "choice": fb_result.choice,
                    "latency_ms": fb_result.latency_ms,
                    "input_tokens": fb_result.input_tokens,
                    "output_tokens": fb_result.output_tokens,
                    "total_tokens": fb_result.total_tokens,
                    "cost": fb_result.cost,
                    "engine": fb_result.engine,
                    "confidence": fb_result.confidence,
                    "pricing_configured": bool((fb_result.metadata or {}).get("pricing_configured", True)),
                    "input_cost_per_million": (fb_result.metadata or {}).get("input_cost_per_million"),
                    "output_cost_per_million": (fb_result.metadata or {}).get("output_cost_per_million"),
                    "pricing_currency": (fb_result.metadata or {}).get("pricing_currency", "UNSPECIFIED"),
                }
                fallback_cache[cache_key] = fallback_record
            if route == "fallback":
                effective_choice = fallback_record["choice"]
                fallback_applied = True
        out.append({
            "id": task.task_id,
            "task_type": task.task_type,
            "expected": case["expected"],
            "predicted": result.choice,
            "raw_predicted": result.choice,
            "effective_predicted": effective_choice,
            "probabilities": result.probabilities,
            "confidence": result.confidence,
            "latency_ms": result.latency_ms,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "total_tokens": result.total_tokens,
            "cost": result.cost,
            "route": route,
            "engine": result.engine,
            "fallback": result.fallback,
            "fallback_applied": fallback_applied,
            "fallback_record": fallback_record,
            "metadata": result.metadata,
        })
    return out


def run_benchmark(
    engines: dict[str, DecisionEngine],
    cases: list[dict],
    *,
    fallback_engines: Mapping[str, DecisionEngine] | None = None,
) -> dict:
    report = {}
    fallback_cache: dict[tuple[str, str], dict] = {}
    fallback_engines = fallback_engines or {}
    for name, engine in engines.items():
        rows = run_engine(
            engine,
            cases,
            fallback_engine=fallback_engines.get(name),
            fallback_cache=fallback_cache,
        )
        report[name] = {"metrics": aggregate(rows), "rows": rows}
    return report


def run_threshold_sweep(
    engine: DecisionEngine,
    cases: list[dict],
    *,
    fallback_engine: DecisionEngine | None,
    thresholds: Iterable[float],
    review_gap: float = 0.20,
) -> dict:
    raw_rows = run_engine(engine, cases, fallback_engine=None, policy=ThresholdPolicy(auto_threshold=1.0, review_threshold=1.0))
    fallback_records: dict[str, dict] = {}
    if fallback_engine is not None and fallback_engine.name != engine.name:
        cache: dict[tuple[str, str], dict] = {}
        all_rows = run_engine(
            engine,
            cases,
            fallback_engine=fallback_engine,
            fallback_cache=cache,
            policy=ThresholdPolicy(auto_threshold=0.0, review_threshold=0.0),
            precompute_fallback=True,
        )
        for row in all_rows:
            record = cache.get((fallback_engine.name, row["id"]))
            if record is not None:
                fallback_records[row["id"]] = record
    pricing = {
        engine.name: {
            "configured": all(bool((row.get("metadata") or {}).get("pricing_configured", True)) for row in raw_rows),
            "input_cost_per_million": next(((row.get("metadata") or {}).get("input_cost_per_million") for row in raw_rows), None),
            "output_cost_per_million": next(((row.get("metadata") or {}).get("output_cost_per_million") for row in raw_rows), None),
        }
    }
    if fallback_engine is not None and fallback_engine.name != engine.name:
        pricing[fallback_engine.name] = {
            "configured": all(bool(record.get("pricing_configured", True)) for record in fallback_records.values()) if fallback_records else True,
            "input_cost_per_million": next((record.get("input_cost_per_million") for record in fallback_records.values() if record.get("input_cost_per_million") is not None), None),
            "output_cost_per_million": next((record.get("output_cost_per_million") for record in fallback_records.values() if record.get("output_cost_per_million") is not None), None),
        }
    from .policy import threshold_sweep
    return {
        "engine": engine.name,
        "rows": raw_rows,
        "pricing": pricing,
        "sweep": threshold_sweep(
            raw_rows, thresholds=thresholds, review_gap=review_gap, fallback_records=fallback_records
        ),
    }
