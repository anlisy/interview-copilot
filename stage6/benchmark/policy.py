from __future__ import annotations

from typing import Iterable, Sequence

from ..decision.calibration import ThresholdPolicy
from .metrics import aggregate


def apply_threshold_policy(
    raw_rows: Sequence[dict],
    *,
    policy: ThresholdPolicy,
    fallback_records: dict[str, dict] | None = None,
) -> list[dict]:
    fallback_records = fallback_records or {}
    out: list[dict] = []
    for row in raw_rows:
        route = policy.route(float(row["confidence"]))
        effective_choice = row["raw_predicted"]
        fallback_record = None
        fallback_applied = False
        if route == "fallback" and row["id"] in fallback_records:
            fallback_record = fallback_records[row["id"]]
            effective_choice = fallback_record["choice"]
            fallback_applied = True
        item = dict(row)
        item.update({
            "route": route,
            "effective_predicted": effective_choice,
            "fallback_record": fallback_record,
            "fallback_applied": fallback_applied,
        })
        out.append(item)
    return out


def summarize_policy(raw_rows: Sequence[dict], policy_rows: Sequence[dict]) -> dict:
    report = aggregate(policy_rows)
    overall = report["overall"]
    auto_rows = [r for r in policy_rows if r["route"] == "auto"]
    review_rows = [r for r in policy_rows if r["route"] == "review"]
    fallback_rows = [r for r in policy_rows if r["route"] == "fallback"]
    overall.update({
        "auto_rate": round(len(auto_rows) / len(policy_rows), 4) if policy_rows else 0.0,
        "review_rate": round(len(review_rows) / len(policy_rows), 4) if policy_rows else 0.0,
        "fallback_candidate_rate": round(len(fallback_rows) / len(policy_rows), 4) if policy_rows else 0.0,
        "fallback_applied_rate": round(sum(bool(r.get("fallback_applied")) for r in policy_rows) / len(policy_rows), 4) if policy_rows else 0.0,
    })
    return report


def threshold_sweep(
    raw_rows: Sequence[dict],
    *,
    thresholds: Iterable[float],
    review_gap: float = 0.20,
    fallback_records: dict[str, dict] | None = None,
) -> list[dict]:
    results = []
    for threshold in thresholds:
        policy = ThresholdPolicy(auto_threshold=float(threshold), review_threshold=max(0.0, float(threshold) - review_gap))
        rows = apply_threshold_policy(raw_rows, policy=policy, fallback_records=fallback_records)
        report = summarize_policy(raw_rows, rows)
        overall = report["overall"]
        results.append({
            "auto_threshold": policy.auto_threshold,
            "review_threshold": policy.review_threshold,
            "accuracy": overall["effective_accuracy"],
            "macro_f1": overall["effective_macro_f1"],
            "raw_accuracy": overall["raw_accuracy"],
            "fallback_gain": overall["fallback_gain"],
            "auto_rate": overall["auto_rate"],
            "review_rate": overall["review_rate"],
            "fallback_candidate_rate": overall["fallback_candidate_rate"],
            "fallback_applied_rate": overall["fallback_applied_rate"],
            "p50_latency_ms": overall["effective_p50_latency_ms"],
            "p95_latency_ms": overall["effective_p95_latency_ms"],
            "avg_input_tokens": overall["effective_avg_input_tokens"],
            "avg_output_tokens": overall["effective_avg_output_tokens"],
            "avg_total_tokens": overall["effective_avg_total_tokens"],
            "avg_cost": overall["effective_avg_cost"],
            "effective_avg_cost": overall["effective_avg_cost"],
            "cost_configured": overall["cost_configured"],
            "pricing_missing_engines": overall["pricing_missing_engines"],
        })
    return results
