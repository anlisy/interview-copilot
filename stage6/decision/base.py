from __future__ import annotations

from abc import ABC, abstractmethod

from .schema import DecisionResult, DecisionTask


class DecisionEngine(ABC):
    name = "base"

    def decide(self, task: DecisionTask) -> DecisionResult:
        task.validate()
        result = self._decide(task)
        result.validate(task.options)
        return result

    @abstractmethod
    def _decide(self, task: DecisionTask) -> DecisionResult:
        raise NotImplementedError
