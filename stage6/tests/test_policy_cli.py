from stage6.decision.calibration import ThresholdPolicy


def test_frozen_policy_is_independent_from_test_outcomes():
    validation = [
        {"confidence": 0.95, "predicted": "a", "expected": "a"},
        {"confidence": 0.90, "predicted": "a", "expected": "a"},
    ]
    from stage6.decision.calibration import calibrate_thresholds
    policy = calibrate_thresholds(validation, min_auto_accuracy=1.0, min_auto_coverage=0.5)
    test = [{"confidence": 0.99, "predicted": "b", "expected": "a"}]
    assert policy.auto_threshold == 0.9
    assert ThresholdPolicy(policy.auto_threshold, policy.review_threshold).route(test[0]["confidence"]) == "auto"
