from __future__ import annotations

from .metrics import accuracy
from ..decision.schema import DecisionResult, DecisionTask


class FixtureGLMEngine:
    name = "glm"

    def __init__(self, *, error_ids: set[str] | None = None, latency_ms: float = 120.0):
        self.error_ids = error_ids or set()
        self.latency_ms = latency_ms

    def decide(self, task: DecisionTask) -> DecisionResult:
        expected = str(task.metadata["expected_choice"])
        choices = list(task.options)
        if task.task_id in self.error_ids and len(choices) > 1:
            choice = choices[1] if choices[0] == expected else choices[0]
        else:
            choice = expected
        probs = {k: 0.03 for k in choices}
        probs[choice] = 0.88
        remainder = 1.0 - probs[choice]
        others = [k for k in choices if k != choice]
        for k in others:
            probs[k] = remainder / max(1, len(others))
        return DecisionResult(
            engine=self.name,
            task_id=task.task_id,
            task_type=task.task_type,
            choice=choice,
            probabilities=probs,
            confidence=max(probs.values()),
            latency_ms=self.latency_ms,
            input_tokens=420,
            output_tokens=52,
            cost=0.0006,
        )


class FixtureJevEngine(FixtureGLMEngine):
    name = "jev"

    def __init__(self, *, error_ids: set[str] | None = None, latency_ms: float = 48.0):
        super().__init__(error_ids=error_ids, latency_ms=latency_ms)
