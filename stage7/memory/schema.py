from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
import hashlib
import re
import uuid


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def normalize_text(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[，。！？；：、“”‘’\"'（）()【】\[\]{}<>《》,.!?;:、]", "", text)
    return text


@dataclass(frozen=True)
class MemoryEvidence:
    """支持长期记忆的原始证据。"""

    source_id: str
    role: str
    content: str
    stage: str | None = None
    timestamp: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MemoryCandidate:
    """从一场 Session 提炼出的候选长期记忆。"""

    content: str
    memory_type: str = "fact"
    confidence: float = 0.8
    importance: float = 0.6
    evidence: list[MemoryEvidence] = field(default_factory=list)
    source_session_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    candidate_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    created_at: str = field(default_factory=_now_iso)

    def __post_init__(self) -> None:
        self.confidence = max(0.0, min(float(self.confidence), 1.0))
        self.importance = max(0.0, min(float(self.importance), 1.0))
        self.content = self.content.strip()

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(normalize_text(self.content).encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["evidence"] = [e.to_dict() if isinstance(e, MemoryEvidence) else e for e in self.evidence]
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryCandidate":
        evidence = [MemoryEvidence(**e) if isinstance(e, dict) else e for e in data.get("evidence", [])]
        payload = dict(data)
        payload["evidence"] = evidence
        return cls(**payload)


@dataclass
class Resolution:
    candidate_id: str
    action: str  # new | duplicate | conflict
    matched_record_id: str | None = None
    reason: str = ""
    similarity: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
