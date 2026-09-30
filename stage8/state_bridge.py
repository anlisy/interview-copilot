from __future__ import annotations

from dataclasses import dataclass
from typing import Any

try:
    from core.state import InterviewState, can_transit
except Exception:  # pragma: no cover
    InterviewState = None  # type: ignore[assignment]
    can_transit = None  # type: ignore[assignment]


@dataclass(frozen=True)
class StateTransition:
    source: str
    target: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {"source": self.source, "target": self.target, "reason": self.reason}


class StateBridge:
    """将 Stage8 可持久化 SessionState 映射到 Stage1 InterviewState。

    Stage1 的 Supervisor/Agent 实例不持久化；这里只同步状态。
    """

    def __init__(self, *, strict: bool = True):
        self.strict = strict

    @staticmethod
    def _stage_name(value: Any) -> str:
        if hasattr(value, "name"):
            return str(value.name)
        return str(value or "INIT")

    @staticmethod
    def _coerce_stage(value: str):
        if InterviewState is None:
            return value
        try:
            return InterviewState[str(value)]
        except Exception:
            try:
                return InterviewState(value)
            except Exception:
                return InterviewState.INIT

    def _record(self, state: Any, source: str, target: str, reason: str) -> None:
        history = state.metadata.setdefault("state_history", [])
        history.append(StateTransition(source, target, reason).to_dict())
        state.workflow_stage = target

    def transition(self, state: Any, target: str, *, reason: str) -> None:
        source = self._stage_name(state.workflow_stage)
        target = self._stage_name(target)
        if source == target:
            return
        if self.strict and can_transit is not None:
            src_enum = self._coerce_stage(source)
            dst_enum = self._coerce_stage(target)
            if not can_transit(src_enum, dst_enum):
                raise RuntimeError(f"非法状态流转: {source} -> {target}")
        self._record(state, source, target, reason)

    def before_agent(self, state: Any, *, agent: str, action: str) -> None:
        if agent == "interviewer" and action == "generate":
            self.transition(state, "GENERATING", reason="stage1 interviewer generate start")
        elif agent == "scorer":
            self.transition(state, "SCORING", reason="stage1 scorer start")
        elif agent == "reviewer" and action == "review":
            if self._stage_name(state.workflow_stage) == "ASKING":
                self.transition(state, "SCORING", reason="review requires scoring boundary")
            self.transition(state, "REVIEWING", reason="stage1 reviewer start")
        elif action == "review":
            self.transition(state, "REVIEWING", reason="online review start")

    def after_agent(self, state: Any, *, agent: str, action: str, finish: bool = False) -> None:
        if agent == "interviewer" and action == "generate":
            self.transition(state, "ASKING", reason="stage1 interviewer generate complete")
        elif agent == "scorer":
            if finish:
                self.transition(state, "REVIEWING", reason="score turn requested session finish")
            else:
                self.transition(state, "ASKING", reason="score complete, continue interview")
        elif agent == "reviewer" and action == "review":
            self.transition(state, "FINISHED", reason="stage1 reviewer complete")
        elif action == "review":
            self.transition(state, "FINISHED", reason="online review complete")

    def before_generic(self, state: Any, *, action: str) -> None:
        if action == "generate" and self._stage_name(state.workflow_stage) == "INIT":
            self.transition(state, "GENERATING", reason="online generate start")
        elif action == "review" and self._stage_name(state.workflow_stage) == "ASKING":
            self.transition(state, "REVIEWING", reason="online review start")

    def after_generic(self, state: Any, *, action: str, finish: bool = False) -> None:
        if action == "generate" and self._stage_name(state.workflow_stage) == "GENERATING":
            self.transition(state, "ASKING", reason="online generate complete")
        if finish:
            current = self._stage_name(state.workflow_stage)
            if current == "ASKING":
                self.transition(state, "SCORING", reason="session finish boundary")
                self.transition(state, "REVIEWING", reason="session finish review boundary")
            if self._stage_name(state.workflow_stage) == "REVIEWING":
                self.transition(state, "FINISHED", reason="online session finished")

    def restore(self, state: Any) -> str:
        return self._stage_name(state.workflow_stage)
