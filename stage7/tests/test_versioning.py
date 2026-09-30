import json

from stage4.memory.memory_store import MemoryStore
from stage7.memory.aggregator import CrossSessionEvidenceAggregator
from stage7.memory.schema import MemoryCandidate, MemoryEvidence
from stage7.memory.versioning import MemoryVersionStore
from stage7.memory.consolidator_b import VersionedMemoryConsolidator
from stage7.memory.extractor import MemoryExtractor
from stage7.memory.checkpoint import CheckpointStore


class FixedExtractor(MemoryExtractor):
    def __init__(self, content):
        self.content = content
        self.calls = 0

    def extract(self, session_id, rows):
        self.calls += 1
        return [MemoryCandidate(
            content=self.content,
            memory_type="skill_strength",
            confidence=0.95,
            importance=0.9,
            source_session_id=session_id,
            evidence=[MemoryEvidence("new-row", "user", self.content)],
            candidate_id="fixed-candidate",
        )]


def test_reinforcement_does_not_append_duplicate_record(tmp_path):
    root = tmp_path / "memory"
    memory = MemoryStore(root)
    old = memory.capture_fact("s-old", "候选人熟悉 Redis 缓存治理", memory_type="skill_strength")
    memory.capture_turn("s-new", "user", "候选人熟悉 Redis 缓存治理", metadata={"memory_candidate": True, "memory_type": "skill_strength"})
    extractor = FixedExtractor("候选人熟悉 Redis 缓存治理")
    result = VersionedMemoryConsolidator(memory, checkpoints=CheckpointStore(root / "checkpoints")).consolidate("s-new", extractor)
    assert result.resolutions[0].action == "reinforce"
    assert result.committed_record_ids == [old.record_id]
    assert len(memory._records) == 1
    state = MemoryVersionStore(root / "versioned").load(old.record_id)
    assert state.evidence_count == 1 or state.evidence_count >= 1
    assert state.current_version == 1


def test_update_creates_new_version_on_same_stable_claim(tmp_path):
    root = tmp_path / "memory"
    memory = MemoryStore(root)
    old = memory.capture_fact("s-old", "候选人熟悉 Redis 缓存治理", memory_type="skill_strength")
    memory.capture_turn("s-new", "user", "候选人熟悉 Redis 缓存治理和缓存击穿治理", metadata={"memory_candidate": True, "memory_type": "skill_strength"})
    extractor = FixedExtractor("候选人熟悉 Redis 缓存治理和缓存击穿治理")
    result = VersionedMemoryConsolidator(memory, checkpoints=CheckpointStore(root / "checkpoints")).consolidate("s-new", extractor)
    assert result.resolutions[0].action == "update"
    assert result.committed_record_ids == [old.record_id]
    assert memory._records[old.record_id].content.endswith("缓存击穿治理")
    versions = MemoryVersionStore(root / "versioned").versions(old.record_id)
    assert [v.version for v in versions] == [1, 2]
    assert versions[1].previous_content == "候选人熟悉 Redis 缓存治理"
    saved = json.loads((root / "durable" / "s-old.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert saved["record_id"] == old.record_id
    assert saved["metadata"]["claim_version"] == 2
