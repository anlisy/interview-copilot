from stage4.memory.memory_store import MemoryStore
from stage7.memory.checkpoint import CheckpointStore
from stage7.memory.consolidator import MemoryConsolidator
from stage7.memory.schema import MemoryCandidate, MemoryEvidence


def test_similar_different_memory_goes_to_conflict(tmp_path):
    memory = MemoryStore(tmp_path / "memory")
    memory.capture_fact("old-session", "Redis 缓存一致性回答完整", memory_type="skill_strength", confidence=0.8)
    c = MemoryConsolidator(memory, checkpoints=CheckpointStore(tmp_path / "memory" / "checkpoints"), similarity_conflict=0.5)
    candidate = MemoryCandidate(
        content="Redis 缓存一致性回答仍不完整",
        memory_type="skill_strength",
        source_session_id="new-session",
        evidence=[MemoryEvidence("r1", "reviewer", "Redis 缓存一致性回答仍不完整")],
    )
    result = c._resolve_one(candidate)
    assert result.action == "conflict"
