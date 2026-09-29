from stage6.benchmark.metrics import aggregate, expected_calibration_error


def test_metrics_include_raw_effective_and_fallback_gain():
    rows = [
        {
            "task_type":"intent","expected":"a","predicted":"a","raw_predicted":"a","effective_predicted":"a",
            "confidence":0.9,"latency_ms":10,"input_tokens":5,"output_tokens":1,"total_tokens":6,"cost":0.1,
            "route":"auto","probabilities":{"a":0.9,"b":0.1},"fallback_applied":False,"fallback_record":None,
        },
        {
            "task_type":"intent","expected":"b","predicted":"a","raw_predicted":"a","effective_predicted":"b",
            "confidence":0.4,"latency_ms":20,"input_tokens":7,"output_tokens":2,"total_tokens":9,"cost":0.2,
            "route":"fallback","probabilities":{"a":0.6,"b":0.4},"fallback_applied":True,
            "fallback_record":{"choice":"b","latency_ms":30,"total_tokens":4,"cost":0.05},
        },
    ]
    result = aggregate(rows)["overall"]
    assert result["raw_accuracy"] == 0.5
    assert result["effective_accuracy"] == 1.0
    assert result["fallback_gain"] == 0.5
    assert result["fallback_applied_rate"] == 0.5
    assert result["avg_fallback_tokens"] == 2.0
    assert expected_calibration_error(rows) > 0


def test_aggregate_includes_effective_end_to_end_metrics():
    rows = [{
        "id": "x", "task_type": "tool", "expected": "a", "predicted": "a",
        "raw_predicted": "a", "effective_predicted": "a", "probabilities": {"a": 1.0},
        "confidence": 1.0, "latency_ms": 100.0, "input_tokens": 10, "output_tokens": 5,
        "total_tokens": 15, "cost": 0.1, "route": "fallback", "fallback_applied": True,
        "fallback_record": {"latency_ms": 900.0, "total_tokens": 20, "cost": 0.2}
    }]
    result = aggregate(rows)["overall"]
    assert result["effective_p50_latency_ms"] == 1000.0
    assert result["effective_p95_latency_ms"] == 1000.0
    assert result["effective_avg_total_tokens"] == 35.0
    assert result["effective_avg_cost"] == 0.3


def test_effective_metrics_include_fallback_latency_tokens_and_cost():
    from stage6.benchmark.metrics import aggregate
    rows = [{
        "id": "x", "task_type": "intent", "expected": "a", "predicted": "b", "raw_predicted": "b",
        "effective_predicted": "a", "confidence": 0.4, "latency_ms": 10, "input_tokens": 100,
        "output_tokens": 20, "total_tokens": 120, "cost": 0.002, "route": "fallback",
        "fallback_applied": True,
        "fallback_record": {"latency_ms": 90, "total_tokens": 30, "cost": 0.003},
        "probabilities": {"a": 0.4, "b": 0.6},
    }]
    result = aggregate(rows)["overall"]
    assert result["effective_p50_latency_ms"] == 100.0
    assert result["effective_avg_total_tokens"] == 150.0
    assert result["effective_avg_cost"] == 0.005


def test_effective_metrics_include_input_and_output_tokens():
    from stage6.benchmark.metrics import aggregate
    rows = [{
        "id": "x", "task_type": "intent", "expected": "a", "predicted": "b", "raw_predicted": "b",
        "effective_predicted": "a", "confidence": 0.4, "latency_ms": 10, "input_tokens": 100,
        "output_tokens": 20, "total_tokens": 120, "cost": 0.002, "route": "fallback", "fallback_applied": True,
        "fallback_record": {"latency_ms": 90, "input_tokens": 30, "output_tokens": 10, "total_tokens": 40, "cost": 0.003},
        "probabilities": {"a": 0.4, "b": 0.6},
    }]
    overall = aggregate(rows)["overall"]
    assert overall["effective_avg_input_tokens"] == 130.0
    assert overall["effective_avg_output_tokens"] == 30.0


def test_unconfigured_cost_is_null_instead_of_zero():
    rows = [{
        "id": "x", "task_type": "intent", "expected": "a", "predicted": "a",
        "raw_predicted": "a", "effective_predicted": "a", "confidence": 0.9,
        "latency_ms": 10, "input_tokens": 100, "output_tokens": 10, "total_tokens": 110,
        "cost": 0.0, "route": "auto", "fallback_applied": False,
        "fallback_record": None, "probabilities": {"a": 1.0},
        "engine": "glm",
        "metadata": {
            "pricing_configured": False,
            "input_cost_per_million": 0.0,
            "output_cost_per_million": 0.0,
        },
    }]
    overall = aggregate(rows)["overall"]
    assert overall["cost_configured"] is False
    assert overall["avg_cost"] is None
    assert overall["effective_avg_cost"] is None
    assert overall["pricing_missing_engines"] == ["glm"]


def test_fallback_unconfigured_cost_is_not_reported_as_zero():
    rows = [{
        "id": "x", "task_type": "intent", "expected": "a", "predicted": "b",
        "raw_predicted": "b", "effective_predicted": "a", "confidence": 0.4,
        "latency_ms": 10, "input_tokens": 100, "output_tokens": 20, "total_tokens": 120,
        "cost": 0.002, "route": "fallback", "fallback_applied": True,
        "probabilities": {"a": 0.4, "b": 0.6}, "engine": "jev",
        "metadata": {"pricing_configured": True, "input_cost_per_million": 0.042, "output_cost_per_million": 0.0},
        "fallback_record": {
            "choice": "a", "latency_ms": 90, "input_tokens": 30, "output_tokens": 10,
            "total_tokens": 40, "cost": 0.0, "engine": "glm", "pricing_configured": False,
        },
    }]
    overall = aggregate(rows)["overall"]
    assert overall["cost_configured"] is False
    assert overall["effective_avg_cost"] is None
    assert overall["pricing_missing_engines"] == ["glm"]
