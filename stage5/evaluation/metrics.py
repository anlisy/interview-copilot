from __future__ import annotations
import math
from typing import Iterable, Sequence


def recall_at_k(relevant: set[str], ranked: Sequence[str], k: int) -> float:
    return len(relevant & set(ranked[:k])) / len(relevant) if relevant else 0.0


def precision_at_k(relevant: set[str], ranked: Sequence[str], k: int) -> float:
    top = list(ranked[:k])
    return len(relevant & set(top)) / len(top) if top else 0.0


def mrr(relevant: set[str], ranked: Sequence[str]) -> float:
    for i, item in enumerate(ranked, 1):
        if item in relevant:
            return 1.0 / i
    return 0.0


def ndcg(graded_relevance: dict[str, float], ranked: Sequence[str], k: int) -> float:
    def gain(rel: float) -> float:
        return (2.0 ** rel) - 1.0

    actual = [float(graded_relevance.get(x, 0.0)) for x in ranked[:k]]
    ideal = sorted((float(v) for v in graded_relevance.values()), reverse=True)[:k]
    def dcg(xs: Sequence[float]) -> float:
        return sum(gain(rel) / math.log2(i + 2) for i, rel in enumerate(xs))
    denom = dcg(ideal)
    return dcg(actual) / denom if denom else 0.0


def fraction(required: Iterable[str], observed: Iterable[str]) -> float:
    required_set = set(required)
    observed_set = set(observed)
    return len(required_set & observed_set) / len(required_set) if required_set else 1.0


def mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def percentile(values: Sequence[float], q: float) -> float:
    if not values:
        return 0.0
    xs = sorted(float(v) for v in values)
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return xs[lo]
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def rate(rows: Sequence[dict], field: str) -> float:
    return mean([1.0 if row.get(field, False) else 0.0 for row in rows])


def unsupported_claim_rate(rows: Sequence[dict]) -> float:
    return mean([1.0 if row.get("unsupported_claims") else 0.0 for row in rows])
