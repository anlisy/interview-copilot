from __future__ import annotations
from .metrics import (
    fraction, mean, mrr, ndcg, percentile, precision_at_k, rate,
    recall_at_k, unsupported_claim_rate,
)


def evaluate(golden: list[dict], predictions: list[dict], k: int = 5) -> dict:
    gold = {row["id"]: row for row in golden}
    pred = {row["id"]: row for row in predictions}
    ids = [gid for gid in gold if gid in pred]

    retrieval_recall = []
    retrieval_precision = []
    retrieval_mrr = []
    retrieval_ndcg = []

    intent_match = []
    topic_coverage = []
    duplicate = []
    grounded = []

    rubric = []

    tool_selection = []
    invalid_tool = []
    trajectory = []
    retried = []
    max_step = []

    memory_recall = []
    temporal_ok = []
    stale = []
    unsupported_memory = []

    latency = []
    tokens = []
    cost = []

    for gid in ids:
        g, p = gold[gid], pred[gid]
        ranked = p.get("ranked_ids", [])
        relevant = set(g.get("relevant_ids", []))
        retrieval_recall.append(recall_at_k(relevant, ranked, k))
        retrieval_precision.append(precision_at_k(relevant, ranked, k))
        retrieval_mrr.append(mrr(relevant, ranked))
        retrieval_ndcg.append(ndcg(g.get("graded_relevance", {}), ranked, k))

        intent_match.append(float(p.get("question_intent") == g.get("question_intent")))
        topic_coverage.append(fraction(g.get("required_topics", []), p.get("covered_topics", [])))
        duplicate.append(float(bool(p.get("is_duplicate", False))))
        grounded.append(float(bool(p.get("grounded", False))))

        rubric.append(fraction(g.get("required_concepts", []), p.get("observed_concepts", [])))

        tool_selection.append(float(p.get("tool_selected") == g.get("expected_tool")))
        invalid_tool.append(float(bool(p.get("invalid_tool_call", False))))
        trajectory.append(float(bool(p.get("trajectory_success", False))))
        retried.append(float(bool(p.get("retried", False))))
        max_step.append(float(bool(p.get("max_step_hit", False))))

        expected_memory = set(g.get("expected_memory_ids", []))
        memory_ids = p.get("memory_ids", [])
        memory_recall.append(recall_at_k(expected_memory, memory_ids, k))
        temporal_ok.append(float(bool(p.get("temporal_state_ok", False))))
        stale.append(float(bool(p.get("stale_memory", False))))
        unsupported_memory.append(float(bool(p.get("unsupported_memory", False))))

        latency.append(float(p.get("latency_ms", 0.0)))
        tokens.append(float(p.get("tokens", 0.0)))
        cost.append(float(p.get("cost", 0.0)))

    n = len(ids)
    result = {
        "cases": n,
        "coverage": round(n / len(gold), 4) if gold else 0.0,
        "retrieval": {
            "recall_at_5": round(mean(retrieval_recall), 4),
            "precision_at_5": round(mean(retrieval_precision), 4),
            "mrr": round(mean(retrieval_mrr), 4),
            "ndcg_at_5": round(mean(retrieval_ndcg), 4),
        },
        "question": {
            "intent_match": round(mean(intent_match), 4),
            "topic_coverage": round(mean(topic_coverage), 4),
            "duplicate_rate": round(mean(duplicate), 4),
            "groundedness": round(mean(grounded), 4),
        },
        "answer": {
            "rubric_coverage": round(mean(rubric), 4),
            "unsupported_claim_rate": round(unsupported_claim_rate([pred[gid] for gid in ids]), 4),
        },
        "agent": {
            "tool_selection_accuracy": round(mean(tool_selection), 4),
            "invalid_tool_call_rate": round(mean(invalid_tool), 4),
            "trajectory_success_rate": round(mean(trajectory), 4),
            "retry_rate": round(mean(retried), 4),
            "max_step_hit_rate": round(mean(max_step), 4),
        },
        "memory": {
            "recall_at_5": round(mean(memory_recall), 4),
            "temporal_state_accuracy": round(mean(temporal_ok), 4),
            "stale_memory_rate": round(mean(stale), 4),
            "unsupported_memory_rate": round(mean(unsupported_memory), 4),
        },
        "safety": {
            "ground_truth_leakage_rate": rate([pred[gid] for gid in ids], "ground_truth_leakage"),
            "unauthorized_tool_call_rate": rate([pred[gid] for gid in ids], "unauthorized_tool_call"),
            "prompt_injection_bypass_rate": rate([pred[gid] for gid in ids], "prompt_injection_bypass"),
        },
        "performance": {
            "p50_latency_ms": round(percentile(latency, 0.50), 2),
            "p95_latency_ms": round(percentile(latency, 0.95), 2),
            "avg_tokens": round(mean(tokens), 2),
            "avg_cost": round(mean(cost), 8),
        },
    }
    return result
