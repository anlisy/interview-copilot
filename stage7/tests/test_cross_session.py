from stage4.memory.memory_store import MemoryStore
from stage7.memory.aggregator import CrossSessionEvidenceAggregator
from stage7.memory.schema import MemoryCandidate, MemoryEvidence


def candidate(session, text, memory_type="skill_strength"):
    return MemoryCandidate(
        content=text,
        memory_type=memory_type,
        source_session_id=session,
        evidence=[MemoryEvidence("r", "user", text)],
    )


def test_same_claim_is_reinforced_across_sessions(tmp_path):
    memory = MemoryStore(tmp_path / "memory")
    memory.capture_fact("s-old", "候选人熟悉 Redis 缓存治理", memory_type="skill_strength")
    out = CrossSessionEvidenceAggregator(memory).aggregate(
        candidate("s-new", "候选人熟悉 Redis 缓存治理")
    )
    assert out.action == "reinforce"
    assert out.source_sessions == ["s-old"]


def test_cross_session_update_keeps_stable_record_id(tmp_path):
    memory = MemoryStore(tmp_path / "memory")
    old = memory.capture_fact("s-old", "候选人熟悉 Redis 缓存治理", memory_type="skill_strength")
    out = CrossSessionEvidenceAggregator(memory).aggregate(
        candidate("s-new", "候选人熟悉 Redis 缓存治理和缓存击穿治理", "skill_strength")
    )
    assert out.action == "update"
    assert out.matched_record_id == old.record_id



def test_paraphrased_same_claim_is_not_split_into_new_claim(tmp_path):
    memory = MemoryStore(tmp_path / "memory")
    old = memory.capture_fact("s-old", "候选人负责过 Redis 缓存治理，解决过缓存击穿问题。", memory_type="verified_experience")
    out = CrossSessionEvidenceAggregator(memory).aggregate(
        candidate("s-new", "之前也处理过 Redis 缓存击穿和热点 Key 保护。", "verified_experience")
    )
    assert out.action == "update"
    assert out.matched_record_id == old.record_id
    assert out.similarity >= 0.45


def test_same_session_memory_is_not_treated_as_cross_session_evidence(tmp_path):
    memory = MemoryStore(tmp_path / "memory")
    memory.capture_fact("s1", "候选人熟悉 Redis 缓存治理", memory_type="skill_strength")
    out = CrossSessionEvidenceAggregator(memory).aggregate(
        candidate("s1", "候选人熟悉 Redis 缓存治理", "skill_strength")
    )
    assert out.action == "new"
