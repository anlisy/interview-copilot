from stage5.evaluation.trace_adapter import build_runtime_evidence, merge_runtime_evidence


def test_runtime_evidence_from_stage1_trace_events():
    events = [
        {"event": "before_action", "agent": "interviewer", "action": "followup", "tool": "memory_search"},
        {"event": "usage", "total_tokens": 120, "cost_usd": 0.0003},
        {"event": "after_action", "status": "success", "latency_ms": 35.5,
         "output_summary": {"items": [{"record_id": "mem-1"}, {"record_id": "mem-2"}]}},
    ]
    out = build_runtime_evidence(events)
    assert out["tool_selected"] == "memory_search"
    assert out["trajectory_success"] is True
    assert out["latency_ms"] == 35.5
    assert out["tokens"] == 120
    assert out["cost"] == 0.0003
    assert out["memory_ids"] == ["mem-1", "mem-2"]


def test_runtime_evidence_detects_policy_and_retry():
    events = [
        {"event": "harness_violation", "message": "Agent 无权调用 Tool=ground_truth_search"},
        {"event": "tool_result", "attempts": 2, "error_code": "tool_error"},
    ]
    out = build_runtime_evidence(events)
    assert out["invalid_tool_call"] is True
    assert out["unauthorized_tool_call"] is True
    assert out["retried"] is True


def test_merge_runtime_fields_override_stale_prediction_values():
    base = {"id": "c1", "tool_selected": "local_rag", "latency_ms": 1}
    evidence = {"tool_selected": "memory_search", "latency_ms": 42}
    merged = merge_runtime_evidence(base, evidence)
    assert merged["tool_selected"] == "memory_search"
    assert merged["latency_ms"] == 42
