from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
import uuid


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class MemoryRecord:
    """长期记忆最小数据单元。"""

    content: str
    session_id: str
    source: str = "interview"
    memory_type: str = "fact"
    turn_id: str | None = None
    stage: str | None = None
    timestamp: str = field(default_factory=utc_now)
    confidence: float = 1.0
    importance: float = 0.5
    status: str = "active"
    metadata: dict[str, Any] = field(default_factory=dict)
    record_id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryRecord":
        return cls(**data)
