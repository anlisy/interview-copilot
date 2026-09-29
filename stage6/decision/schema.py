from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class DecisionTask:
    task_id: str
    task_type: str
    state: str | Mapping[str, Any]
    options: Mapping[str, str]
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.task_id:
            raise ValueError("task_id is required")
        if self.task_type not in {"skill", "tool", "intent"}:
            raise ValueError(f"unsupported task_type={self.task_type}")
        if not self.options:
            raise ValueError("options cannot be empty")
        if len(self.options) > 255:
            raise ValueError("options exceed JEV Choice limit of 255")
        if any(not k or not v for k, v in self.options.items()):
            raise ValueError("option ids/descriptions must be non-empty")
        if self.task_type == "intent":
            if not isinstance(self.state, Mapping):
                raise ValueError("intent state must be an object containing question_a and question_b")
            for key in ("question_a", "question_b"):
                value = self.state.get(key)
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(f"intent state missing non-empty {key}")


@dataclass(frozen=True)
class DecisionResult:
    engine: str
    task_id: str
    task_type: str
    choice: str
    probabilities: dict[str, float]
    confidence: float
    latency_ms: float
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0
    fallback: bool = False
    fallback_reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def validate(self, options: Mapping[str, str]) -> None:
        if self.choice not in options:
            raise ValueError(f"decision choice={self.choice!r} not in allowed options")
        probs = {str(k): float(v) for k, v in self.probabilities.items()}
        if any(v < 0 or v > 1 for v in probs.values()):
            raise ValueError("probabilities must be in [0, 1]")
        if probs:
            total = sum(probs.values())
            if abs(total - 1.0) > 0.05:
                raise ValueError(f"probabilities must sum close to 1, got {total}")
        if not 0 <= float(self.confidence) <= 1:
            raise ValueError("confidence must be in [0, 1]")
        if self.latency_ms < 0:
            raise ValueError("latency_ms cannot be negative")
        if self.input_tokens < 0 or self.output_tokens < 0:
            raise ValueError("token counts cannot be negative")


class DecisionError(RuntimeError):
    pass


class DecisionEngineUnavailable(DecisionError):
    pass
