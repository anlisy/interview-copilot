from stage4.memory.memory_store import MemoryStore
from stage7.memory.aggregator import CrossSessionEvidenceAggregator
from stage7.memory.schema import MemoryCandidate, MemoryEvidence
from stage7.memory.versioning import MemoryVersionStore


def test_cross_session_conflict_is_not_auto_overwritten(tmp_path):
    root = tmp_path / "memory"
    memory = MemoryStore(root)
    old = memory.capture_fact("s-old", "候选人完整掌握 Redis 缓存治理", memory_type="skill_strength")
    candidate = MemoryCandidate(
        content="候选人掌握 Redis 缓存治理不完整",
        memory_type="skill_strength",
        source_session_id="s-new",
        evidence=[MemoryEvidence("r", "user", "候选人掌握 Redis 缓存治理不完整")],
    )
    decision = CrossSessionEvidenceAggregator(memory, update_threshold=0.5).aggregate(candidate)
    assert decision.action == "conflict"
    store = MemoryVersionStore(root / "versioned")
    store.apply(memory, candidate, action="conflict", matched_record_id=old.record_id, reason=decision.reason)
    assert memory._records[old.record_id].content == "候选人完整掌握 Redis 缓存治理"
    assert list((root / "durable").glob("*.jsonl")) == [root / "durable" / "s-old.jsonl"]
    assert (root / "versioned" / "conflicts" / f"{old.record_id}.jsonl").exists()
