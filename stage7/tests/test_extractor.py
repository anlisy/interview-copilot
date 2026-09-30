from stage7.memory.extractor import RuleMemoryExtractor


def test_rule_extractor_only_uses_explicit_candidates():
    rows = [
        {"record": {"record_id": "a", "stage": "ANSWER", "confidence": 0.7, "importance": 0.4}, "role": "user", "content": "普通回答", "extra": {}},
        {"record": {"record_id": "b", "stage": "REVIEW", "confidence": 0.9, "importance": 0.8}, "role": "assistant", "content": "Redis 缓存击穿治理是薄弱点", "extra": {"memory_candidate": True, "memory_type": "weakness", "importance": 0.85}},
    ]
    out = RuleMemoryExtractor().extract("s1", rows)
    assert len(out) == 1
    assert out[0].memory_type == "weakness"
    assert out[0].evidence[0].source_id == "b"
