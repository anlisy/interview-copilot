from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping


JSON_TYPES = frozenset({"object", "array", "string", "number", "integer", "boolean", "null"})


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    allowed_agents: frozenset[str] = frozenset()
    eval_deny: bool = False
    eval_only: bool = False
    allowed_actions: Mapping[str, frozenset[str]] = field(default_factory=dict)
    timeout_sec: float = 10.0
    retries: int = 0
    idempotent: bool = True
    source: str = "local"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("tool name 不能为空")
        if self.timeout_sec <= 0:
            raise ValueError("timeout_sec 必须 > 0")
        if self.retries < 0 or self.retries > 3:
            raise ValueError("retries 必须在 0~3")
        if self.input_schema.get("type") != "object":
            raise ValueError("input_schema 根节点必须是 object")
        output_type = self.output_schema.get("type")
        if output_type not in JSON_TYPES:
            raise ValueError(f"output_schema 根节点类型不受支持: {output_type}")
        actions = dict(self.allowed_actions)
        for agent, agent_actions in actions.items():
            if agent not in self.allowed_agents:
                raise ValueError(f"allowed_actions[{agent}] 必须同时出现在 allowed_agents 中")
            if not agent_actions:
                raise ValueError(f"allowed_actions[{agent}] 不能为空")


@dataclass(frozen=True)
class ToolCallContext:
    agent: str
    eval_mode: bool = False
    deadline_ms: int | None = None
    session_id: str | None = None
    trace_id: str | None = None
    action: str | None = None
    principal_type: str = "agent"


@dataclass(frozen=True)
class ToolResult:
    tool: str
    ok: bool
    output: Any = None
    error_code: str | None = None
    error_message: str | None = None
    attempts: int = 0
    latency_ms: int = 0
    blocked: bool = False
    untrusted_output: bool = True
    executed: bool = False


ToolHandler = Callable[[dict[str, Any]], Any]
