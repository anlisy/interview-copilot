from stage5.evaluation.evaluator import evaluate


def test_multidimensional_eval():
    golden = [{
        "id": "x", "canonical_question": "q", "question_intent": "intent",
        "relevant_ids": ["a"], "graded_relevance": {"a": 3},
        "required_concepts": ["c1", "c2"], "required_topics": ["t1"],
        "disallowed_claims": [], "expected_tool": "local_rag",
        "expected_memory_ids": ["m1"],
    }]
    predictions = [{
        "id": "x", "ranked_ids": ["a"], "question_intent": "intent",
        "covered_topics": ["t1"], "is_duplicate": False, "grounded": True,
        "observed_concepts": ["c1"], "unsupported_claims": [],
        "tool_selected": "local_rag", "invalid_tool_call": False,
        "trajectory_success": True, "retried": False, "max_step_hit": False,
        "latency_ms": 100, "tokens": 10, "cost": 0.01,
        "memory_ids": ["m1"], "temporal_state_ok": True,
        "stale_memory": False, "unsupported_memory": False,
        "ground_truth_leakage": False, "unauthorized_tool_call": False,
        "prompt_injection_bypass": False,
    }]
    out = evaluate(golden, predictions)
    assert out["retrieval"]["recall_at_5"] == 1.0
    assert out["answer"]["rubric_coverage"] == 0.5
    assert out["agent"]["tool_selection_accuracy"] == 1.0
