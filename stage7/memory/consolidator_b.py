from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from stage4.memory.memory_store import MemoryStore
from stage4.memory.raw_store import RawTrajectoryStore

from .aggregator import CrossSessionEvidenceAggregator
from .checkpoint import CheckpointStore
from .extractor import MemoryExtractor
from .schema import MemoryCandidate, Resolution
from .versioning import MemoryVersionStore
from .consolidator import MemoryConsolidator


@dataclass
class VersionedConsolidationResult:
    session_id: str
    job_id: str
    source_fingerprint: str
    status: str
    candidates: list[MemoryCandidate] = field(default_factory=list)
    aggregations: list[dict[str, Any]] = field(default_factory=list)
    resolutions: list[Resolution] = field(default_factory=list)
    committed_record_ids: list[str] = field(default_factory=list)
    conflict_candidate_ids: list[str] = field(default_factory=list)
    version_updates: list[dict[str, Any]] = field(default_factory=list)
    resumed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "job_id": self.job_id,
            "source_fingerprint": self.source_fingerprint,
            "status": self.status,
            "candidates": [c.to_dict() for c in self.candidates],
            "aggregations": self.aggregations,
            "resolutions": [r.to_dict() for r in self.resolutions],
            "committed_record_ids": self.committed_record_ids,
            "conflict_candidate_ids": self.conflict_candidate_ids,
            "version_updates": self.version_updates,
            "resumed": self.resumed,
        }


class VersionedMemoryConsolidator:
    """Stage7-B：跨 Session evidence 聚合 + stable claim versioning。"""

    POLICY_VERSION = "stage7-b-evidence-version-v1"

    def __init__(
        self,
        memory: MemoryStore,
        *,
        raw_store: RawTrajectoryStore | None = None,
        checkpoints: CheckpointStore | None = None,
        versions: MemoryVersionStore | None = None,
        aggregator: CrossSessionEvidenceAggregator | None = None,
    ):
        self.memory = memory
        self.raw = raw_store or memory.raw
        self.checkpoints = checkpoints or CheckpointStore(self.memory.root / "checkpoints")
        self.versions = versions or MemoryVersionStore(self.memory.root / "versioned")
        self.aggregator = aggregator or CrossSessionEvidenceAggregator(self.memory)
        self._base = MemoryConsolidator(self.memory, raw_store=self.raw, checkpoints=self.checkpoints)

    def _job_id(self, session_id: str, fingerprint: str) -> str:
        return "stage7b-" + __import__("hashlib").sha256(f"{self.POLICY_VERSION}:{session_id}:{fingerprint}".encode("utf-8")).hexdigest()[:24]

    def consolidate(self, session_id: str, extractor: MemoryExtractor, *, resume: bool = True) -> VersionedConsolidationResult:
        rows = self.raw.read(session_id)
        fingerprint = self._base._fingerprint(rows)
        job_id = self._job_id(session_id, fingerprint)
        checkpoint = self.checkpoints.load(job_id) if resume else None
        resumed = checkpoint is not None

        if checkpoint and checkpoint.get("status") == "committed":
            return self._result_from_checkpoint(session_id, job_id, fingerprint, checkpoint, resumed=True)

        if checkpoint and checkpoint.get("candidates") is not None:
            candidates = [MemoryCandidate.from_dict(x) for x in checkpoint.get("candidates", [])]
        else:
            candidates = extractor.extract(session_id, rows)
            self.checkpoints.save(job_id, {
                "policy_version": self.POLICY_VERSION,
                "source_fingerprint": fingerprint,
                "status": "extracted",
                "candidates": [c.to_dict() for c in candidates],
            })

        if checkpoint and checkpoint.get("aggregations") is not None:
            aggregations = list(checkpoint.get("aggregations", []))
            resolutions = [Resolution(**x) for x in checkpoint.get("resolutions", [])]
        else:
            agg = [self.aggregator.aggregate(c) for c in candidates]
            aggregations = [a.to_dict() for a in agg]
            resolutions = [a.to_resolution() for a in agg]
            self.checkpoints.save(job_id, {
                "policy_version": self.POLICY_VERSION,
                "source_fingerprint": fingerprint,
                "status": "resolved",
                "candidates": [c.to_dict() for c in candidates],
                "aggregations": aggregations,
                "resolutions": [r.to_dict() for r in resolutions],
                "version_updates": checkpoint.get("version_updates", []) if checkpoint else [],
                "committed_record_ids": checkpoint.get("committed_record_ids", []) if checkpoint else [],
                "conflict_candidate_ids": checkpoint.get("conflict_candidate_ids", []) if checkpoint else [],
                "applied_candidates": checkpoint.get("applied_candidates", []) if checkpoint else [],
            })

        by_id = {c.candidate_id: c for c in candidates}
        applied = set(checkpoint.get("applied_candidates", [])) if checkpoint else set()
        committed = list(checkpoint.get("committed_record_ids", [])) if checkpoint else []
        conflicts = list(checkpoint.get("conflict_candidate_ids", [])) if checkpoint else []
        version_updates = list(checkpoint.get("version_updates", [])) if checkpoint else []

        self.checkpoints.save(job_id, {
            "policy_version": self.POLICY_VERSION,
            "source_fingerprint": fingerprint,
            "status": "committing",
            "candidates": [c.to_dict() for c in candidates],
            "aggregations": aggregations,
            "resolutions": [r.to_dict() for r in resolutions],
            "version_updates": version_updates,
            "committed_record_ids": committed,
            "conflict_candidate_ids": conflicts,
            "applied_candidates": sorted(applied),
        })

        for resolution in resolutions:
            candidate = by_id[resolution.candidate_id]
            if candidate.candidate_id in applied:
                continue
            action = resolution.action
            record_id, version, _state = self.versions.apply(
                self.memory,
                candidate,
                action=action,
                matched_record_id=resolution.matched_record_id,
                reason=resolution.reason,
            )
            applied.add(candidate.candidate_id)
            update = {
                "candidate_id": candidate.candidate_id,
                "action": action,
                "record_id": record_id,
                "version": version,
                "matched_record_id": resolution.matched_record_id,
                "reason": resolution.reason,
            }
            version_updates.append(update)
            if action == "conflict":
                if candidate.candidate_id not in conflicts:
                    conflicts.append(candidate.candidate_id)
            elif record_id not in committed:
                committed.append(record_id)

            self.checkpoints.save(job_id, {
                "policy_version": self.POLICY_VERSION,
                "source_fingerprint": fingerprint,
                "status": "committing",
                "candidates": [c.to_dict() for c in candidates],
                "aggregations": aggregations,
                "resolutions": [r.to_dict() for r in resolutions],
                "version_updates": version_updates,
                "committed_record_ids": committed,
                "conflict_candidate_ids": conflicts,
                "applied_candidates": sorted(applied),
            })

        self.checkpoints.save(job_id, {
            "policy_version": self.POLICY_VERSION,
            "source_fingerprint": fingerprint,
            "status": "committed",
            "candidates": [c.to_dict() for c in candidates],
            "aggregations": aggregations,
            "resolutions": [r.to_dict() for r in resolutions],
            "version_updates": version_updates,
            "committed_record_ids": committed,
            "conflict_candidate_ids": conflicts,
            "applied_candidates": sorted(applied),
        })
        return VersionedConsolidationResult(
            session_id=session_id,
            job_id=job_id,
            source_fingerprint=fingerprint,
            status="committed",
            candidates=candidates,
            aggregations=aggregations,
            resolutions=resolutions,
            committed_record_ids=committed,
            conflict_candidate_ids=conflicts,
            version_updates=version_updates,
            resumed=resumed,
        )

    @staticmethod
    def _result_from_checkpoint(session_id, job_id, fingerprint, checkpoint, resumed):
        return VersionedConsolidationResult(
            session_id=session_id,
            job_id=job_id,
            source_fingerprint=fingerprint,
            status="committed",
            candidates=[MemoryCandidate.from_dict(x) for x in checkpoint.get("candidates", [])],
            aggregations=list(checkpoint.get("aggregations", [])),
            resolutions=[Resolution(**x) for x in checkpoint.get("resolutions", [])],
            committed_record_ids=list(checkpoint.get("committed_record_ids", [])),
            conflict_candidate_ids=list(checkpoint.get("conflict_candidate_ids", [])),
            version_updates=list(checkpoint.get("version_updates", [])),
            resumed=resumed,
        )
