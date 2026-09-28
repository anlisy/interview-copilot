from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SkillMetadata:
    name: str
    description: str
    path: Path
    signals: tuple[str, ...] = ()
    intents: tuple[str, ...] = ()
    allowed_actions: tuple[str, ...] = ()
    version: str = "1.0"
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SkillCandidate:
    skill: SkillMetadata
    score: float
    matched_signals: tuple[str, ...] = ()
    matched_intents: tuple[str, ...] = ()
    reason_code: str = "fallback"


@dataclass(frozen=True)
class SkillActivation:
    metadata: SkillMetadata
    content: str
    skill_dir: Path
