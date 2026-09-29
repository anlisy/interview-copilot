from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence


@dataclass(frozen=True)
class ThresholdPolicy:
    auto_threshold: float = 0.90
    review_threshold: float = 0.70

    def __post_init__(self) -> None:
        if not 0.0 <= self.review_threshold <= self.auto_threshold <= 1.0:
            raise ValueError("thresholds must satisfy 0 <= review <= auto <= 1")

    def route(self, confidence: float) -> str:
        if confidence >= self.auto_threshold:
            return "auto"
        if confidence >= self.review_threshold:
            return "review"
        return "fallback"


def _accuracy(rows: Sequence[dict]) -> float:
    return sum(r["predicted"] == r["expected"] for r in rows) / len(rows) if rows else 0.0


def reliability_bins(rows: Sequence[dict], *, bins: int = 10) -> list[dict]:
    buckets = [[] for _ in range(bins)]
    for row in rows:
        confidence = max(0.0, min(1.0, float(row["confidence"])))
        idx = min(bins - 1, int(confidence * bins))
        buckets[idx].append(row)
    out: list[dict] = []
    for index, bucket in enumerate(buckets):
        if not bucket:
            out.append({
                "bin": index,
                "lower": round(index / bins, 3),
                "upper": round((index + 1) / bins, 3),
                "count": 0,
                "accuracy": 0.0,
                "avg_confidence": 0.0,
                "gap": 0.0,
            })
            continue
        accuracy = _accuracy(bucket)
        confidence = sum(float(r["confidence"]) for r in bucket) / len(bucket)
        out.append({
            "bin": index,
            "lower": round(index / bins, 3),
            "upper": round((index + 1) / bins, 3),
            "count": len(bucket),
            "accuracy": round(accuracy, 4),
            "avg_confidence": round(confidence, 4),
            "gap": round(abs(accuracy - confidence), 4),
        })
    return out


def normalize_threshold_candidates(threshold_candidates: Iterable[float]) -> list[float]:
    values = sorted({round(float(value), 3) for value in threshold_candidates})
    if not values:
        raise ValueError("threshold_candidates cannot be empty")
    if any(value < 0.0 or value > 1.0 for value in values):
        raise ValueError("threshold candidates must be within [0, 1]")
    return values


def calibrate_thresholds(
    rows: Sequence[dict],
    *,
    min_auto_accuracy: float = 0.95,
    min_auto_coverage: float = 0.60,
    review_gap: float = 0.20,
    threshold_candidates: Sequence[float] | None = None,
) -> ThresholdPolicy:
    if not rows:
        if threshold_candidates is None:
            return ThresholdPolicy()
        candidate_values = normalize_threshold_candidates(threshold_candidates)
        selected = candidate_values[-1]
        return ThresholdPolicy(
            auto_threshold=selected,
            review_threshold=max(0.0, round(selected - review_gap, 3)),
        )

    if threshold_candidates is None:
        candidates = sorted({round(float(r["confidence"]), 3) for r in rows}, reverse=True)
        constrained = False
    else:
        candidates = normalize_threshold_candidates(threshold_candidates)
        constrained = True

    feasible: list[tuple[float, float, float]] = []
    evaluated: list[tuple[float, float, float]] = []
    for threshold in candidates:
        selected = [r for r in rows if float(r["confidence"]) >= threshold]
        if not selected:
            coverage = 0.0
            accuracy = 0.0
        else:
            accuracy = _accuracy(selected)
            coverage = len(selected) / len(rows)
        evaluated.append((threshold, accuracy, coverage))
        if accuracy >= min_auto_accuracy and coverage >= min_auto_coverage:
            feasible.append((threshold, accuracy, coverage))

    if feasible:
        # Prefer the largest auto coverage; for equal coverage use the lower threshold.
        best, _, _ = max(feasible, key=lambda item: (item[2], -item[0]))
    elif evaluated:
        # No candidate satisfies the constraints: remain inside the tested candidate set.
        # Prefer highest accuracy, then highest coverage, then lower threshold.
        best, _, _ = max(evaluated, key=lambda item: (item[1], item[2], -item[0]))
    else:
        best = candidates[-1] if candidates else 0.99

    # With explicit candidates, this value is guaranteed to be one of the tested thresholds.
    if constrained and best not in candidates:
        raise AssertionError("calibrated threshold must come from threshold_candidates")

    review = max(0.0, round(best - review_gap, 3))
    return ThresholdPolicy(auto_threshold=round(best, 3), review_threshold=review)


def calibration_report(
    rows: Sequence[dict],
    *,
    bins: int = 10,
    min_auto_accuracy: float = 0.95,
    min_auto_coverage: float = 0.60,
    review_gap: float = 0.20,
    threshold_candidates: Sequence[float] | None = None,
) -> dict:
    policy = calibrate_thresholds(
        rows,
        min_auto_accuracy=min_auto_accuracy,
        min_auto_coverage=min_auto_coverage,
        review_gap=review_gap,
        threshold_candidates=threshold_candidates,
    )
    auto_rows = [r for r in rows if float(r["confidence"]) >= policy.auto_threshold]
    auto_accuracy = round(_accuracy(auto_rows), 4) if auto_rows else 0.0
    auto_coverage = round(len(auto_rows) / len(rows), 4) if rows else 0.0
    return {
        "cases": len(rows),
        "auto_threshold": policy.auto_threshold,
        "review_threshold": policy.review_threshold,
        "threshold_candidates": list(threshold_candidates) if threshold_candidates is not None else None,
        "selected_from_candidates": threshold_candidates is not None,
        "auto_accuracy": auto_accuracy,
        "auto_coverage": auto_coverage,
        "constraints_satisfied": auto_accuracy >= min_auto_accuracy and auto_coverage >= min_auto_coverage,
        "reliability_bins": reliability_bins(rows, bins=bins),
    }
