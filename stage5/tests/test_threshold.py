from stage5.evaluation.threshold_calibrator import calibrate


def test_threshold_calibration():
    rows = [
        {"similarity": 0.9, "label": 1},
        {"similarity": 0.8, "label": 1},
        {"similarity": 0.6, "label": 0},
        {"similarity": 0.3, "label": 0},
    ]
    result = calibrate(rows)
    assert 0.6 <= result["threshold"] <= 0.9
    assert result["f1"] > 0
