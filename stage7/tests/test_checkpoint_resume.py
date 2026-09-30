import json

from stage4.memory.memory_store import MemoryStore
from stage7.memory.checkpoint import CheckpointStore
from stage7.memory.consolidator import MemoryConsolidator
from stage7.memory.extractor import MemoryExtractor
from stage7.memory.schema import MemoryCandidate, MemoryEvidence, Resolution


class OneCandidateExtractor(MemoryExtractor):
    def extract(self, session_id, rows):
        return [MemoryCandidate(
            content="候选人明确负责 Redis 缓存治理",
            memory_type="verified_experience",
            confidence=0.95,
            importance=0.9,
            source_session_id=session_id,
            evidence=[MemoryEvidence("r1", "user", "候选人明确负责 Redis 缓存治理")],
            candidate_id="candidate-fixed",
        )]


def test_resume_from_committing_checkpoint_does_not_duplicate(tmp_path):
    memory = MemoryStore(tmp_path / "memory")
    session = "s1"
    memory.capture_turn(session, "user", "done", metadata={})
    checkpoints = CheckpointStore(tmp_path / "memory" / "checkpoints")
    c = MemoryConsolidator(memory, checkpoints=checkpoints)
    candidates = OneCandidateExtractor().extract(session, [])
    fingerprint = c._fingerprint(memory.raw.read(session))
    job_id = c._job_id(session, fingerprint)
    candidate = candidates[0]
    checkpoint = {
        "policy_version": c.POLICY_VERSION,
        "source_fingerprint": fingerprint,
        "status": "committing",
        "candidates": [candidate.to_dict()],
        "resolutions": [Resolution(candidate.candidate_id, "new").to_dict()],
        "committed_record_ids": [],
        "committed_candidates": {},
        "conflict_candidate_ids": [],
    }
    checkpoints.save(job_id, checkpoint)
    # 模拟 checkpoint 更新丢失：先把 Durable Memory 写进去，但 checkpoint 仍显示未提交。
    record = memory.capture_fact(session, candidate.content, memory_type=candidate.memory_type,
                                confidence=candidate.confidence, importance=candidate.importance,
                                metadata={"stage7_candidate_id": candidate.candidate_id})
    result = c.consolidate(session, OneCandidateExtractor())
    assert result.status == "committed"
    assert len(memory._records) == 1  # checkpoint 丢失时仍不会重复写 Durable Memory
    assert result.resolutions[0].action == "new"  # 原 checkpoint 的 decision 不变，但 commit 通过 candidate_id 幂等检查复用已有记录
    payload = json.loads(checkpoints._path(job_id).read_text(encoding="utf-8"))
    assert payload["status"] == "committed"
    assert payload["committed_candidates"][candidate.candidate_id] == record.record_id
