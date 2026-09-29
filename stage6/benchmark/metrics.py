from __future__ import annotations

import math
from collections import defaultdict
from typing import Iterable, Sequence


def accuracy(rows: Sequence[dict]) -> float:
    return sum(r["predicted"] == r["expected"] for r in rows) / len(rows) if rows else 0.0


def macro_f1(rows: Sequence[dict]) -> float:
    labels = sorted({r["expected"] for r in rows} | {r["predicted"] for r in rows})
    vals = []
    for label in labels:
        tp = sum(r["predicted"] == label and r["expected"] == label for r in rows)
        fp = sum(r["predicted"] == label and r["expected"] != label for r in rows)
        fn = sum(r["predicted"] != label and r["expected"] == label for r in rows)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        vals.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)
    return sum(vals) / len(vals) if vals else 0.0




def _accuracy_field(rows: Sequence[dict], field: str) -> float:
    if not rows:
        return 0.0
    return sum(r.get(field, r.get("predicted")) == r["expected"] for r in rows) / len(rows)


def _macro_f1_field(rows: Sequence[dict], field: str) -> float:
    if not rows:
        return 0.0
    labels = sorted({r["expected"] for r in rows} | {r.get(field, r.get("predicted")) for r in rows})
    vals = []
    for label in labels:
        tp = sum(r.get(field, r.get("predicted")) == label and r["expected"] == label for r in rows)
        fp = sum(r.get(field, r.get("predicted")) == label and r["expected"] != label for r in rows)
        fn = sum(r.get(field, r.get("predicted")) != label and r["expected"] == label for r in rows)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        vals.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)
    return sum(vals) / len(vals) if vals else 0.0

def confusion_matrix(rows: Sequence[dict]) -> dict[str, dict[str, int]]:
    labels = sorted({r["expected"] for r in rows} | {r["predicted"] for r in rows})
    return {
        actual: {pred: sum(r["expected"] == actual and r["predicted"] == pred for r in rows) for pred in labels}
        for actual in labels
    }


def percentile(values: Sequence[float], q: float) -> float:
    if not values:
        return 0.0
    xs = sorted(float(x) for x in values)
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return xs[lo]
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def expected_calibration_error(rows: Sequence[dict], bins: int = 10) -> float:
    if not rows:
        return 0.0
    buckets = [[] for _ in range(bins)]
    for row in rows:
        conf = max(0.0, min(1.0, float(row["confidence"])))
        idx = min(bins - 1, int(conf * bins))
        buckets[idx].append(row)
    total = len(rows)
    ece = 0.0
    for bucket in buckets:
        if not bucket:
            continue
        acc = accuracy(bucket)
        conf = sum(float(r["confidence"]) for r in bucket) / len(bucket)
        ece += (len(bucket) / total) * abs(acc - conf)
    return ece


def brier_score(rows: Sequence[dict]) -> float:
    if not rows:
        return 0.0
    labels = sorted({r["expected"] for r in rows})
    total = 0.0
    for r in rows:
        probs = r.get("probabilities", {})
        for label in labels:
            y = 1.0 if label == r["expected"] else 0.0
            p = float(probs.get(label, 0.0))
            total += (p - y) ** 2
    return total / len(rows)


def _pricing_configured(row: dict) -> bool:
    metadata = row.get("metadata") or {}
    # Real engines explicitly report whether a unit price is configured.
    # Fixture/Rule rows predate this field; their hard-coded zero/non-zero costs are known.
    base_configured = bool(metadata.get("pricing_configured", True))
    fallback = row.get("fallback_record") or {}
    fallback_configured = bool(fallback.get("pricing_configured", True))
    return base_configured and fallback_configured


def _pricing_missing_engines(row: dict) -> set[str]:
    missing: set[str] = set()
    metadata = row.get("metadata") or {}
    if not bool(metadata.get("pricing_configured", True)):
        missing.add(str(row.get("engine", "unknown")))
    fallback = row.get("fallback_record") or {}
    if fallback and not bool(fallback.get("pricing_configured", True)):
        missing.add(str(fallback.get("engine", "unknown")))
    return missing


def aggregate(rows: Sequence[dict]) -> dict:
    task_groups = defaultdict(list)
    for row in rows:
        task_groups[row["task_type"]].append(row)
    def summarize(group: Sequence[dict]) -> dict:
        raw_acc = _accuracy_field(group, "raw_predicted")
        effective_acc = _accuracy_field(group, "effective_predicted")
        effective_latencies = [
            float(r["latency_ms"]) + float((r.get("fallback_record") or {}).get("latency_ms", 0.0))
            for r in group
        ]
        effective_input_tokens = [
            int(r["input_tokens"]) + int((r.get("fallback_record") or {}).get("input_tokens", 0))
            for r in group
        ]
        effective_output_tokens = [
            int(r["output_tokens"]) + int((r.get("fallback_record") or {}).get("output_tokens", 0))
            for r in group
        ]
        effective_tokens = [
            int(r["total_tokens"]) + int((r.get("fallback_record") or {}).get("total_tokens", 0))
            for r in group
        ]
        cost_configured = all(_pricing_configured(r) for r in group) if group else True
        pricing_missing_engines = sorted({engine for r in group for engine in _pricing_missing_engines(r)})
        raw_costs = [float(r["cost"]) for r in group]
        effective_costs = [
            float(r["cost"]) + float((r.get("fallback_record") or {}).get("cost", 0.0))
            for r in group
        ]
        return {
            "cases": len(group),
            "accuracy": round(raw_acc, 4),
            "macro_f1": round(_macro_f1_field(group, "raw_predicted"), 4),
            "raw_accuracy": round(raw_acc, 4),
            "raw_macro_f1": round(_macro_f1_field(group, "raw_predicted"), 4),
            "effective_accuracy": round(effective_acc, 4),
            "effective_macro_f1": round(_macro_f1_field(group, "effective_predicted"), 4),
            "fallback_gain": round(effective_acc - raw_acc, 4),
            "fallback_applied_rate": round(sum(bool(r.get("fallback_applied")) for r in group) / len(group), 4) if group else 0.0,
            "ece": round(expected_calibration_error(group), 4),
            "brier": round(brier_score(group), 4),
            "p50_latency_ms": round(percentile([r["latency_ms"] for r in group], 0.50), 3),
            "p95_latency_ms": round(percentile([r["latency_ms"] for r in group], 0.95), 3),
            "effective_p50_latency_ms": round(percentile(effective_latencies, 0.50), 3),
            "effective_p95_latency_ms": round(percentile(effective_latencies, 0.95), 3),
            "avg_input_tokens": round(sum(r["input_tokens"] for r in group) / len(group), 2) if group else 0.0,
            "avg_output_tokens": round(sum(r["output_tokens"] for r in group) / len(group), 2) if group else 0.0,
            "avg_total_tokens": round(sum(r["total_tokens"] for r in group) / len(group), 2) if group else 0.0,
            "effective_avg_input_tokens": round(sum(effective_input_tokens) / len(group), 2) if group else 0.0,
            "effective_avg_output_tokens": round(sum(effective_output_tokens) / len(group), 2) if group else 0.0,
            "effective_avg_total_tokens": round(sum(effective_tokens) / len(group), 2) if group else 0.0,
            "cost_configured": cost_configured,
            "pricing_missing_engines": pricing_missing_engines,
            "avg_cost": round(sum(raw_costs) / len(group), 8) if group and cost_configured else None,
            "effective_avg_cost": round(sum(effective_costs) / len(group), 8) if group and cost_configured else None,
            "avg_fallback_latency_ms": round(sum((r.get("fallback_record") or {}).get("latency_ms", 0.0) for r in group) / len(group), 3) if group else 0.0,
            "avg_fallback_tokens": round(sum((r.get("fallback_record") or {}).get("total_tokens", 0) for r in group) / len(group), 2) if group else 0.0,
            "fallback_candidate_rate": round(sum(r["route"] == "fallback" for r in group) / len(group), 4) if group else 0.0,
            "fallback_rate": round(sum(bool(r.get("fallback_applied")) for r in group) / len(group), 4) if group else 0.0,
            "confusion_matrix": confusion_matrix(group),
            "effective_confusion_matrix": {
                actual: {pred: sum(r.get("effective_predicted", r["predicted"]) == pred and r["expected"] == actual for r in group)
                         for pred in sorted({r.get("effective_predicted", r["predicted"]) for r in group} | {r["expected"] for r in group})}
                for actual in sorted({r["expected"] for r in group})
            },
        }
    return {
        "cases": len(rows),
        "overall": summarize(rows),
        "by_task": {task: summarize(group) for task, group in sorted(task_groups.items())},
    }
