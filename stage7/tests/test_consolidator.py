from stage4.memory.memory_store import MemoryStore
from stage7.memory.checkpoint import CheckpointStore
from stage7.memory.consolidator import MemoryConsolidator
from stage7.memory.extractor import MemoryExtractor
from stage7.memory.schema import MemoryCandidate, MemoryEvidence


class FakeExtractor(MemoryExtractor):
    calls = 0

    def extract(self, session_id, rows):
        type(self).calls += 1
        return [
            MemoryCandidate(
                content="候选人熟悉 Redis 缓存治理",
                memory_type="skill_strength",
                confidence=0.9,
                importance=0.8,
                source_session_id=session_id,
                evidence=[MemoryEvidence("r1", "user", "候选人熟悉 Redis 缓存治理")],
            )
        ]


def test_consolidation_commits_and_is_idempotent(tmp_path):
    memory = MemoryStore(tmp_path / "memory")
    session = "s1"
    memory.capture_turn(session, "user", "候选人熟悉 Redis 缓存治理", metadata={"memory_candidate": True, "memory_type": "skill_strength", "importance": 0.8})
    checkpoints = CheckpointStore(tmp_path / "memory" / "checkpoints")
    c = MemoryConsolidator(memory, checkpoints=checkpoints)
    FakeExtractor.calls = 0
    first = c.consolidate(session, FakeExtractor())
    second = c.consolidate(session, FakeExtractor())
    assert first.status == "committed"
    assert len(first.committed_record_ids) == 1
    assert second.resumed is True
    assert second.committed_record_ids == first.committed_record_ids
    assert FakeExtractor.calls == 1
