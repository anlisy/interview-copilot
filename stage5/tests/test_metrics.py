from stage5.evaluation.metrics import (
    mrr, ndcg, precision_at_k, recall_at_k, fraction, percentile
)


def test_retrieval_metrics():
    rel = {"a", "c"}
    ranked = ["b", "a", "c"]
    assert recall_at_k(rel, ranked, 3) == 1.0
    assert precision_at_k(rel, ranked, 2) == 0.5
    assert mrr(rel, ranked) == 0.5
    assert ndcg({"a": 3, "c": 2}, ranked, 3) > 0


def test_fraction_and_percentile():
    assert fraction({"a", "b"}, {"a", "c"}) == 0.5
    assert abs(percentile([1, 2, 3, 4], 0.95) - 3.85) < 1e-9
