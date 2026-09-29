from __future__ import annotations

import re
import time

from .base import DecisionEngine
from .schema import DecisionResult, DecisionTask


def _terms(text: str) -> set[str]:
    s = (text or "").lower()
    terms = set(re.findall(r"[a-z0-9_]+", s))
    for chunk in re.findall(r"[\u4e00-\u9fff]+", s):
        terms.update(chunk)
        terms.update(chunk[i : i + 2] for i in range(len(chunk) - 1))
    return {x for x in terms if x}


def _score(option_text: str, state: str) -> float:
    state_terms = _terms(state)
    option_terms = _terms(option_text)
    if not state_terms or not option_terms:
        return 0.0
    return len(state_terms & option_terms) / len(state_terms)


class RuleDecisionEngine(DecisionEngine):
    """Deterministic baseline using the option descriptions supplied by the application."""

    name = "rule"

    def _decide(self, task: DecisionTask) -> DecisionResult:
        start = time.perf_counter()
        state = task.state if isinstance(task.state, str) else str(dict(task.state))
        scores = {key: _score(desc, state) for key, desc in task.options.items()}

        # Allow benchmark/tool metadata to define explicit rules without embedding labels in engine code.
        for key, desc in task.options.items():
            bonus_terms = task.metadata.get("rule_keywords", {}).get(key, [])
            if any(term.lower() in state.lower() for term in bonus_terms):
                scores[key] += 0.5

        ordered = sorted(scores.items(), key=lambda x: (-x[1], x[0]))
        top_key, top_score = ordered[0]
        second_score = ordered[1][1] if len(ordered) > 1 else 0.0
        raw = {key: max(0.0, value) for key, value in scores.items()}
        total = sum(raw.values())
        if total <= 0:
            probabilities = {key: (1.0 if key == top_key else 0.0) for key in scores}
            confidence = 0.5
        else:
            probabilities = {key: value / total for key, value in raw.items()}
            confidence = min(1.0, 0.5 + max(0.0, top_score - second_score))

        latency = (time.perf_counter() - start) * 1000
        return DecisionResult(
            engine=self.name,
            task_id=task.task_id,
            task_type=task.task_type,
            choice=top_key,
            probabilities={k: round(v, 6) for k, v in probabilities.items()},
            confidence=round(confidence, 6),
            latency_ms=round(latency, 3),
        )
