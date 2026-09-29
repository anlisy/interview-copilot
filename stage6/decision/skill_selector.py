from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from .base import DecisionEngine
from .schema import DecisionTask


@dataclass(frozen=True)
class DecisionSkillSelection:
    selected: Any
    alternatives: tuple[Any, ...]
    margin: float
    confidence: float
    route: str


class DecisionSkillSelector:
    """Adapter for Stage2 ManagedRuntime; keeps Skill candidate generation unchanged."""

    def __init__(self, engine: DecisionEngine, *, min_confidence: float = 0.70):
        self.engine = engine
        self.min_confidence = min_confidence

    def select(self, candidates: Sequence[Any], *, task_text: str = "") -> DecisionSkillSelection:
        if not candidates:
            raise LookupError("没有 Skill 候选")
        options = {
            candidate.skill.name: candidate.skill.description
            for candidate in candidates
        }
        task = DecisionTask(
            task_id=f"skill:{task_text[:60]}",
            task_type="skill",
            state=task_text,
            options=options,
        )
        result = self.engine.decide(task)
        ordered = sorted(candidates, key=lambda x: result.probabilities.get(x.skill.name, 0.0), reverse=True)
        selected = next((x for x in candidates if x.skill.name == result.choice), ordered[0])
        second = result.probabilities.get(ordered[1].skill.name, 0.0) if len(ordered) > 1 else 0.0
        margin = round(result.probabilities.get(selected.skill.name, 0.0) - second, 4)
        route = "auto" if result.confidence >= self.min_confidence else "fallback"
        return DecisionSkillSelection(selected, tuple(x for x in ordered if x is not selected), margin, result.confidence, route)
