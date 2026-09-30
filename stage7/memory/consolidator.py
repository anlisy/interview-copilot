from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import hashlib
import json
from difflib import SequenceMatcher

from stage4.memory.memory_store import MemoryStore
from stage4.memory.raw_store import RawTrajectoryStore

from .checkpoint import CheckpointStore
from .extractor import MemoryExtractor
from .schema import MemoryCandidate, Resolution, normalize_text


@dataclass
class ConsolidationResult:
    session_id: str
    job_id: str
    source_fingerprint: str
    status: str
    candidates: list[MemoryCandidate] = field(default_factory=list)
    resolutions: list[Resolution] = field(default_factory=list)
    committed_record_ids: list[str] = field(default_factory=list)
    conflict_candidate_ids: list[str] = field(default_factory=list)
    resumed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "job_id": self.job_id,
            "source_fingerprint": self.source_fingerprint,
            "status": self.status,
            "candidates": [c.to_dict() for c in self.candidates],
            "resolutions": [r.to_dict() for r in self.resolutions],
            "committed_record_ids": self.committed_record_ids,
            "conflict_candidate_ids": self.conflict_candidate_ids,
            "resumed": self.resumed,
        }


class MemoryConsolidator:
    """Stage7-A：跨 Session 安全沉淀，不自动解决语义冲突。"""

    POLICY_VERSION = "stage7-a-safe-v1"

    def __init__(
        self,
        memory: MemoryStore,
        *,
        raw_store: RawTrajectoryStore | None = None,
        checkpoints: CheckpointStore | None = None,
        similarity_duplicate: float = 0.92,
        similarity_conflict: float = 0.65,
    ):
        self.memory = memory
        self.raw = raw_store or memory.raw
        self.checkpoints = checkpoints or CheckpointStore()
        self.similarity_duplicate = similarity_duplicate
        self.similarity_conflict = similarity_conflict

    @staticmethod
    def _fingerprint(rows: list[dict[str, Any]]) -> str:
        canonical = []
        for row in rows:
            record = row.get("record") or {}
            canonical.append({
                "record_id": record.get("record_id"),
                "role": row.get("role"),
                "content": row.get("content", ""),
                "extra": row.get("extra") or {},
            })
        blob = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def _job_id(self, session_id: str, fingerprint: str) -> str:
        raw = f"{self.POLICY_VERSION}:{session_id}:{fingerprint}"
        return "stage7-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]

    def _resolve_one(self, candidate: MemoryCandidate) -> Resolution:
        exact_query = candidate.content
        hits = self.memory.recall(exact_query, limit=10)
        candidate_norm = normalize_text(candidate.content)
        best_ratio = 0.0
        best = None
        for hit in hits:
            if hit.get("memory_type") != candidate.memory_type:
                continue
            content = str(hit.get("content") or "")
            ratio = SequenceMatcher(None, candidate_norm, normalize_text(content)).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best = hit

        if best:
            best_text = str(best.get("content") or "")
            if _looks_contradictory(candidate.content, best_text):
                return Resolution(candidate.candidate_id, "conflict", best.get("record_id"), "high semantic overlap but explicit polarity/negation differs", best_ratio)
            if best_ratio >= self.similarity_duplicate:
                return Resolution(candidate.candidate_id, "duplicate", best.get("record_id"), "same memory type and near-identical content", best_ratio)
            if best_ratio >= self.similarity_conflict:
                return Resolution(candidate.candidate_id, "conflict", best.get("record_id"), "same memory type but content needs semantic review", best_ratio)
        return Resolution(candidate.candidate_id, "new", None, "no sufficiently similar active memory found", best_ratio)

    def consolidate(
        self,
        session_id: str,
        extractor: MemoryExtractor,
        *,
        resume: bool = True,
    ) -> ConsolidationResult:
        rows = self.raw.read(session_id)
        fingerprint = self._fingerprint(rows)
        job_id = self._job_id(session_id, fingerprint)
        checkpoint = self.checkpoints.load(job_id) if resume else None
        resumed = checkpoint is not None

        if checkpoint and checkpoint.get("status") == "committed":
            return ConsolidationResult(
                session_id=session_id,
                job_id=job_id,
                source_fingerprint=fingerprint,
                status="committed",
                candidates=[MemoryCandidate.from_dict(x) for x in checkpoint.get("candidates", [])],
                resolutions=[Resolution(**x) for x in checkpoint.get("resolutions", [])],
                committed_record_ids=list(checkpoint.get("committed_record_ids", [])),
                conflict_candidate_ids=list(checkpoint.get("conflict_candidate_ids", [])),
                resumed=True,
            )

        if checkpoint and checkpoint.get("status") in {"extracted", "resolved"}:
            candidates = [MemoryCandidate.from_dict(x) for x in checkpoint.get("candidates", [])]
        else:
            candidates = extractor.extract(session_id, rows)
            self.checkpoints.save(job_id, {
                "policy_version": self.POLICY_VERSION,
                "source_fingerprint": fingerprint,
                "status": "extracted",
                "candidates": [c.to_dict() for c in candidates],
            })

        if checkpoint and checkpoint.get("status") in {"resolved", "committing"}:
            resolutions = [Resolution(**x) for x in checkpoint.get("resolutions", [])]
        else:
            resolutions = [self._resolve_one(candidate) for candidate in candidates]
            self.checkpoints.save(job_id, {
                "policy_version": self.POLICY_VERSION,
                "source_fingerprint": fingerprint,
                "status": "resolved",
                "candidates": [c.to_dict() for c in candidates],
                "resolutions": [r.to_dict() for r in resolutions],
            })

        committed: list[str] = list(checkpoint.get("committed_record_ids", [])) if checkpoint else []
        conflicts: list[str] = list(checkpoint.get("conflict_candidate_ids", [])) if checkpoint else []
        committed_candidates: dict[str, str] = dict(checkpoint.get("committed_candidates", {})) if checkpoint else {}
        by_id = {c.candidate_id: c for c in candidates}

        # 标记进入逐候选提交阶段；即使进程中断，也能从 committed_candidates 继续。
        self.checkpoints.save(job_id, {
            "policy_version": self.POLICY_VERSION,
            "source_fingerprint": fingerprint,
            "status": "committing",
            "candidates": [c.to_dict() for c in candidates],
            "resolutions": [r.to_dict() for r in resolutions],
            "committed_record_ids": committed,
            "committed_candidates": committed_candidates,
            "conflict_candidate_ids": conflicts,
        })

        for resolution in resolutions:
            candidate = by_id[resolution.candidate_id]
            if resolution.action == "new":
                if candidate.candidate_id in committed_candidates:
                    continue
                # 即使 checkpoint 恰好丢失，也先检查 Durable Memory 中是否已有本候选。
                existing_id = _find_stage7_candidate(self.memory, candidate.candidate_id)
                if existing_id:
                    record_id = existing_id
                else:
                    record = self.memory.capture_fact(
                        session_id=session_id,
                        content=candidate.content,
                        confidence=candidate.confidence,
                        importance=candidate.importance,
                        memory_type=candidate.memory_type,
                        metadata={
                            **candidate.metadata,
                            "stage7_candidate_id": candidate.candidate_id,
                            "evidence": [e.to_dict() for e in candidate.evidence],
                            "consolidation_policy": self.POLICY_VERSION,
                        },
                    )
                    record_id = record.record_id
                committed_candidates[candidate.candidate_id] = record_id
                if record_id not in committed:
                    committed.append(record_id)
            elif resolution.action == "duplicate" and resolution.matched_record_id:
                committed_candidates.setdefault(candidate.candidate_id, resolution.matched_record_id)
                if resolution.matched_record_id not in committed:
                    committed.append(resolution.matched_record_id)
            elif resolution.action == "conflict" and candidate.candidate_id not in conflicts:
                conflicts.append(candidate.candidate_id)

            # 每处理一个候选就落 checkpoint，缩小故障重放窗口。
            self.checkpoints.save(job_id, {
                "policy_version": self.POLICY_VERSION,
                "source_fingerprint": fingerprint,
                "status": "committing",
                "candidates": [c.to_dict() for c in candidates],
                "resolutions": [r.to_dict() for r in resolutions],
                "committed_record_ids": committed,
                "committed_candidates": committed_candidates,
                "conflict_candidate_ids": conflicts,
            })

        self.checkpoints.save(job_id, {
            "policy_version": self.POLICY_VERSION,
            "source_fingerprint": fingerprint,
            "status": "committed",
            "candidates": [c.to_dict() for c in candidates],
            "resolutions": [r.to_dict() for r in resolutions],
            "committed_record_ids": committed,
            "committed_candidates": committed_candidates,
            "conflict_candidate_ids": conflicts,
        })
        return ConsolidationResult(
            session_id=session_id,
            job_id=job_id,
            source_fingerprint=fingerprint,
            status="committed",
            candidates=candidates,
            resolutions=resolutions,
            committed_record_ids=committed,
            conflict_candidate_ids=conflicts,
            resumed=resumed,
        )


def _looks_contradictory(a: str, b: str) -> bool:
    """轻量冲突启发式：只识别明显的正/负极性对，不声称替代语义模型。"""
    positive = ("完整", "熟悉", "掌握", "正确", "较强", "充分", "解决了", "通过")
    negative = ("不完整", "不熟悉", "未掌握", "不正确", "较弱", "不足", "薄弱", "错误", "没解决", "未通过")
    a_pos = any(x in a for x in positive)
    a_neg = any(x in a for x in negative)
    b_pos = any(x in b for x in positive)
    b_neg = any(x in b for x in negative)
    return (a_pos and b_neg) or (a_neg and b_pos)


def _find_stage7_candidate(memory: MemoryStore, candidate_id: str) -> str | None:
    """查找已经写入 Durable Memory 的 Stage7 candidate，避免 crash/retry 导致重复写入。"""
    records = getattr(memory, "_records", {})
    for record in records.values():
        if (record.metadata or {}).get("stage7_candidate_id") == candidate_id:
            return record.record_id
    return None
