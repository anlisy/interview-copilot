from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
import re
from typing import Any

from stage4.memory.memory_store import MemoryStore

from .schema import MemoryCandidate, Resolution, normalize_text
from .consolidator import _looks_contradictory


@dataclass
class EvidenceAggregate:
    """跨 Session 对同一候选事实进行证据聚合。"""

    candidate_id: str
    action: str  # new | reinforce | update | conflict
    matched_record_id: str | None = None
    similarity: float = 0.0
    evidence_count: int = 0
    source_sessions: list[str] = field(default_factory=list)
    reason: str = ""

    def to_resolution(self) -> Resolution:
        return Resolution(
            candidate_id=self.candidate_id,
            action=self.action,
            matched_record_id=self.matched_record_id,
            reason=self.reason,
            similarity=self.similarity,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "action": self.action,
            "matched_record_id": self.matched_record_id,
            "similarity": self.similarity,
            "evidence_count": self.evidence_count,
            "source_sessions": self.source_sessions,
            "reason": self.reason,
        }


class CrossSessionEvidenceAggregator:
    """在所有 Session 的 Durable Memory 上做保守匹配。"""

    def __init__(
        self,
        memory: MemoryStore,
        *,
        duplicate_threshold: float = 0.92,
        update_threshold: float = 0.45,
        recall_limit: int = 20,
    ):
        self.memory = memory
        self.duplicate_threshold = duplicate_threshold
        self.update_threshold = update_threshold
        self.recall_limit = recall_limit

    def aggregate(self, candidate: MemoryCandidate) -> EvidenceAggregate:
        hits = self.memory.recall(candidate.content, limit=self.recall_limit)
        candidate_norm = normalize_text(candidate.content)
        best = None
        best_ratio = 0.0
        for hit in hits:
            if hit.get("memory_type") != candidate.memory_type:
                continue
            source_session = str(hit.get("session_id") or "")
            if source_session == candidate.source_session_id:
                continue
            if hit.get("status", "active") != "active":
                continue
            content = str(hit.get("content") or "")
            ratio = _similarity(candidate_norm, normalize_text(content))
            if ratio > best_ratio:
                best_ratio = ratio
                best = hit

        if not best:
            return EvidenceAggregate(
                candidate_id=candidate.candidate_id,
                action="new",
                reason="no cross-session memory with sufficient overlap",
            )

        source_session = str(best.get("session_id") or "")
        best_content = str(best.get("content") or "")

        # 冲突优先于 reinforce/update：高重合但明确出现正负极性变化时不自动覆盖。
        if best_ratio >= self.update_threshold and _looks_contradictory(candidate.content, best_content):
            return EvidenceAggregate(
                candidate_id=candidate.candidate_id,
                action="conflict",
                matched_record_id=str(best.get("record_id")),
                similarity=best_ratio,
                evidence_count=1,
                source_sessions=[source_session] if source_session else [],
                reason="high cross-session overlap but explicit polarity/negation differs",
            )

        # duplicate 只代表接近同文复述。
        # 不再使用综合 overlap 直接判 duplicate，避免“旧事实 + 新细节”被吞成 reinforce。
        sequence_ratio = _sequence_ratio(candidate_norm, normalize_text(best_content))
        if sequence_ratio >= self.duplicate_threshold:
            return EvidenceAggregate(
                candidate_id=candidate.candidate_id,
                action="reinforce",
                matched_record_id=str(best.get("record_id")),
                similarity=best_ratio,
                evidence_count=1,
                source_sessions=[source_session] if source_session else [],
                reason="same claim repeated across sessions with near-identical wording; reinforce evidence instead of appending duplicate memory",
            )

        if best_ratio >= self.update_threshold:
            return EvidenceAggregate(
                candidate_id=candidate.candidate_id,
                action="update",
                matched_record_id=str(best.get("record_id")),
                similarity=best_ratio,
                evidence_count=1,
                source_sessions=[source_session] if source_session else [],
                reason="same memory type with substantial overlap; create a new version on the stable claim",
            )

        return EvidenceAggregate(
            candidate_id=candidate.candidate_id,
            action="new",
            reason="cross-session overlap below update threshold",
        )


def _sequence_ratio(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _similarity(a: str, b: str) -> float:
    """估计“同一 Claim”的重合度；不直接使用任一单项覆盖率。"""
    if not a or not b:
        return 0.0
    sequence = _sequence_ratio(a, b)
    a_clean = _clean_for_overlap(a)
    b_clean = _clean_for_overlap(b)
    if not a_clean or not b_clean:
        return sequence

    a_chars, b_chars = set(a_clean), set(b_clean)
    char_coverage = len(a_chars & b_chars) / min(len(a_chars), len(b_chars))

    a2 = _bigrams(a_clean)
    b2 = _bigrams(b_clean)
    bigram_coverage = len(a2 & b2) / min(len(a2), len(b2)) if a2 and b2 else 0.0

    # 字符顺序反映改写程度；字符覆盖和二元片段覆盖反映关键事实重合。
    # 权重保持简单、可解释，作为无模型 Rule baseline，而不是伪装成语义模型。
    return 0.45 * sequence + 0.35 * char_coverage + 0.20 * bigram_coverage


def _clean_for_overlap(text: str) -> str:
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]", "", text.lower())


def _bigrams(text: str) -> set[str]:
    return {text[i:i + 2] for i in range(len(text) - 1)}
