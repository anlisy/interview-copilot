from __future__ import annotations

from dataclasses import dataclass

from .tool_models import ToolCallContext, ToolSpec
from .tool_registry import ToolRegistry


class ToolPolicyViolation(PermissionError):
    pass


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason_code: str
    message: str


@dataclass
class ToolPolicy:
    default_deny: bool = True

    def decide(self, spec: ToolSpec, ctx: ToolCallContext) -> PolicyDecision:
        if ctx.principal_type not in {"agent", "evaluator", "system"}:
            return PolicyDecision(False, "unknown_principal_type", f"未知 principal_type={ctx.principal_type}")
        if spec.eval_only and (ctx.principal_type != "evaluator" or not ctx.eval_mode):
            return PolicyDecision(False, "eval_only_denied", f"Tool={spec.name} 仅允许受控 Eval 组件调用")
        if ctx.eval_mode and spec.eval_deny:
            return PolicyDecision(False, "eval_tool_denied", f"Eval 模式禁止 Tool: {spec.name}")
        if spec.allowed_agents and ctx.agent not in spec.allowed_agents:
            return PolicyDecision(False, "agent_acl_denied", f"Agent={ctx.agent} 无权调用 Tool={spec.name}")
        if self.default_deny and not spec.allowed_agents:
            return PolicyDecision(False, "no_acl", f"Tool={spec.name} 未配置允许 Agent")
        if ctx.action is not None:
            if not spec.allowed_actions:
                return PolicyDecision(False, "action_acl_missing", f"Tool={spec.name} 未配置 action ACL，拒绝在 action={ctx.action} 下调用")
            allowed_actions = spec.allowed_actions.get(ctx.agent, frozenset())
            if ctx.action not in allowed_actions:
                return PolicyDecision(False, "action_acl_denied", f"Agent={ctx.agent} 在 action={ctx.action} 下无权调用 Tool={spec.name}")
        return PolicyDecision(True, "allowed", "allow")

    def check(self, spec: ToolSpec, ctx: ToolCallContext) -> None:
        decision = self.decide(spec, ctx)
        if not decision.allowed:
            raise ToolPolicyViolation(f"{decision.reason_code}: {decision.message}")

    def visible_tools(self, registry: ToolRegistry, ctx: ToolCallContext) -> tuple[str, ...]:
        visible: list[str] = []
        for spec in (registry.get(name) for name in registry.names()):
            if self.decide(spec, ctx).allowed:
                visible.append(spec.name)
        return tuple(visible)
