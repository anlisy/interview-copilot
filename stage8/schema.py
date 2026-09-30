from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class RouteResult:
    kind: str
    choice: str
    confidence: float
    route: str
    engine: str
    task_id: str
    latency_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0
    fallback: bool = False
    reason: str = ""
    alternatives: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def decision_route(self) -> str:
        """推荐名称：表示决策策略路径，而非执行引擎 fallback。"""
        return self.route

    @property
    def fallback_applied(self) -> bool:
        """推荐名称：表示是否真的发生了 fallback engine 执行。"""
        return self.fallback

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["alternatives"] = list(self.alternatives)
        data["decision_route"] = self.route
        data["fallback_applied"] = self.fallback
        return data


@dataclass
class SessionState:
    session_id: str
    workflow_stage: str = "INIT"
    turn_count: int = 0
    last_question: str = ""
    last_answer: str = ""
    last_user_answer: str = ""
    last_skill: str = ""
    last_tool: str = ""
    last_intent: str = ""
    updated_at: str = ""
    recent_questions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SessionState":
        fields = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**fields)


@dataclass
class AgentTextResult:
    text: str
    engine: str = "glm"
    latency_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def to_dict(self) -> dict[str, Any]:
        return asdict(self) | {"total_tokens": self.total_tokens}


@dataclass
class OnlineTurnResult:
    session_id: str
    turn_id: str
    task: str
    state: SessionState
    skill: RouteResult | None
    tool: RouteResult | None
    intent: RouteResult | None
    context_memories: list[dict[str, Any]]
    agent_output: AgentTextResult
    trace_id: str
    consolidation: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "turn_id": self.turn_id,
            "task": self.task,
            "state": self.state.to_dict(),
            "skill": self.skill.to_dict() if self.skill else None,
            "tool": self.tool.to_dict() if self.tool else None,
            "intent": self.intent.to_dict() if self.intent else None,
            "context_memories": self.context_memories,
            "agent_output": self.agent_output.to_dict(),
            "trace_id": self.trace_id,
            "consolidation": self.consolidation,
        }
