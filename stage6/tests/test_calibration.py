from stage6.decision.calibration import ThresholdPolicy, calibrate_thresholds


def test_threshold_policy_routes_three_bands():
    policy = ThresholdPolicy(0.9, 0.7)
    assert policy.route(0.95) == "auto"
    assert policy.route(0.8) == "review"
    assert policy.route(0.5) == "fallback"


def test_calibration_uses_validation_rows():
    rows = [
        {"confidence": 0.95, "predicted": "a", "expected": "a"},
        {"confidence": 0.92, "predicted": "a", "expected": "a"},
        {"confidence": 0.75, "predicted": "a", "expected": "b"},
        {"confidence": 0.60, "predicted": "b", "expected": "a"},
    ]
    policy = calibrate_thresholds(rows, min_auto_accuracy=0.95, min_auto_coverage=0.5)
    assert policy.auto_threshold >= 0.92
    assert policy.review_threshold < policy.auto_threshold


def test_calibration_threshold_must_come_from_actual_sweep_candidates():
    rows = [
        {"confidence": 0.91, "predicted": "a", "expected": "a"},
        {"confidence": 0.81, "predicted": "a", "expected": "a"},
        {"confidence": 0.71, "predicted": "a", "expected": "a"},
        {"confidence": 0.61, "predicted": "a", "expected": "b"},
        {"confidence": 0.51, "predicted": "a", "expected": "b"},
    ]
    candidates = [0.50, 0.70, 0.80, 0.90]
    policy = calibrate_thresholds(
        rows,
        min_auto_accuracy=0.95,
        min_auto_coverage=0.60,
        threshold_candidates=candidates,
    )
    assert policy.auto_threshold == 0.7
    assert policy.auto_threshold in candidates
