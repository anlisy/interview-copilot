from stage5.evaluation.gate import check_gate


def test_gate_absolute_and_relative():
    cfg = {
        "absolute": {
            "retrieval.recall_at_5": {"direction": "max", "threshold": 0.8},
            "safety.ground_truth_leakage_rate": {"direction": "min", "threshold": 0.0},
        },
        "relative": {
            "performance.p95_latency_ms": {"direction": "min", "max_increase": 0.15},
        },
    }
    current = {
        "retrieval": {"recall_at_5": 0.9},
        "safety": {"ground_truth_leakage_rate": 0.0},
        "performance": {"p95_latency_ms": 110.0},
    }
    baseline = {"performance": {"p95_latency_ms": 100.0}}
    out = check_gate(current, cfg, baseline)
    assert out.passed
