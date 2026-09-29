from stage6.benchmark.policy import apply_threshold_policy, threshold_sweep
from stage6.decision.calibration import ThresholdPolicy


def test_policy_routes_and_keeps_raw_choice_without_fallback():
    rows = [{"id": "a", "expected": "x", "raw_predicted": "x", "predicted": "x", "confidence": 0.8,
             "latency_ms": 10, "total_tokens": 100, "cost": 0.1, "task_type": "skill"}]
    out = apply_threshold_policy(rows, policy=ThresholdPolicy(auto_threshold=0.9, review_threshold=0.7))
    assert out[0]["route"] == "review"
    assert out[0]["effective_predicted"] == "x"
    assert out[0]["fallback_applied"] is False


def test_threshold_sweep_applies_fallback_only_below_review():
    rows = [
        {"id": "a", "expected": "x", "raw_predicted": "x", "predicted": "x", "confidence": 0.95,
         "latency_ms": 10, "input_tokens": 50, "output_tokens": 50, "total_tokens": 100, "cost": 0.1, "task_type": "skill"},
        {"id": "b", "expected": "x", "raw_predicted": "y", "predicted": "y", "confidence": 0.50,
         "latency_ms": 10, "input_tokens": 50, "output_tokens": 50, "total_tokens": 100, "cost": 0.1, "task_type": "skill"},
    ]
    fallback = {"b": {"choice": "x", "latency_ms": 20, "total_tokens": 20, "cost": 0.01}}
    out = threshold_sweep(rows, thresholds=[0.9], fallback_records=fallback)
    assert out[0]["fallback_applied_rate"] == 0.5
    assert out[0]["accuracy"] == 1.0


def test_calibration_reliability_bins_include_empty_bins():
    from stage6.decision.calibration import reliability_bins
    bins = reliability_bins([
        {"confidence": 0.95, "predicted": "a", "expected": "a"},
        {"confidence": 0.55, "predicted": "a", "expected": "b"},
    ], bins=5)
    assert len(bins) == 5
    assert sum(item["count"] for item in bins) == 2


def test_threshold_sweep_exposes_cost_configuration_status():
    rows = [{
        "id": "a", "expected": "x", "raw_predicted": "x", "predicted": "x", "confidence": 0.95,
        "latency_ms": 10, "input_tokens": 50, "output_tokens": 50, "total_tokens": 100,
        "cost": 0.1, "task_type": "skill", "engine": "glm",
        "metadata": {"pricing_configured": False},
    }]
    out = threshold_sweep(rows, thresholds=[0.9])
    assert out[0]["cost_configured"] is False
    assert out[0]["effective_avg_cost"] is None
    assert out[0]["pricing_missing_engines"] == ["glm"]
