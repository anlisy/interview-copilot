from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class WorkflowError(ValueError):
    pass


class Workflow:
    def __init__(self, data: dict[str, Any]):
        self.data = data or {}
        self.version = int(self.data.get("version", 1))
        self.name = str(self.data.get("name", "interview-copilot"))
        self.stages = self.data.get("stages") or {}
        self.limits = self.data.get("limits") or {}
        self.eval_policy = self.data.get("eval_policy") or {}
        self.tools = self.data.get("tools") or {}
        self.actions = self.data.get("actions") or {}
        if not self.stages:
            raise WorkflowError("workflow.yaml 缺少 stages")
        self._validate()

    def _validate(self) -> None:
        stage_names = set(self.stages)
        tool_names = set(self.tools)
        action_names = set(self.actions)
        for stage_name, stage in self.stages.items():
            if not isinstance(stage, dict):
                raise WorkflowError(f"阶段 {stage_name} 配置必须是 object")
            for action in stage.get("allowed_actions", []):
                if action not in action_names:
                    raise WorkflowError(f"阶段 {stage_name} 引用了不存在 action={action}")
            for tool in stage.get("allowed_tools", []):
                if tool not in tool_names:
                    raise WorkflowError(f"阶段 {stage_name} 引用了不存在 tool={tool}")
            for dst in stage.get("next_stages", []):
                if dst not in stage_names:
                    raise WorkflowError(f"阶段 {stage_name} 引用了不存在 next_stage={dst}")
            if not isinstance(stage.get("allowed_agents", []), list):
                raise WorkflowError(f"阶段 {stage_name} allowed_agents 必须是 list")
        for action_name, action in self.actions.items():
            if not isinstance(action, dict):
                raise WorkflowError(f"action {action_name} 配置必须是 object")
            timeout = action.get("timeout_seconds")
            if timeout is not None and float(timeout) <= 0:
                raise WorkflowError(f"action {action_name} timeout_seconds 必须 > 0")

    @classmethod
    def load(cls, path: str | Path) -> "Workflow":
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(p)
        with p.open("r", encoding="utf-8") as f:
            return cls(yaml.safe_load(f) or {})

    def stage(self, name: str) -> dict[str, Any]:
        try:
            return self.stages[name]
        except KeyError as exc:
            raise WorkflowError(f"未知阶段: {name}") from exc

    def is_agent_allowed(self, stage: str, agent: str) -> bool:
        return agent in self.stage(stage).get("allowed_agents", [])

    def is_action_allowed(self, stage: str, action: str) -> bool:
        return action in self.stage(stage).get("allowed_actions", [])

    def is_tool_allowed(self, stage: str, tool: str | None) -> bool:
        if tool is None:
            return True
        allowed = self.stage(stage).get("allowed_tools")
        if allowed is None:
            return True
        return tool in allowed

    def can_transition(self, src: str, dst: str) -> bool:
        return dst in self.stage(src).get("next_stages", [])

    def max_steps(self) -> int:
        return int(self.limits.get("max_steps", 40))

    def max_followup(self) -> int:
        return int(self.limits.get("max_followup", 2))

    def token_budget(self) -> int:
        return int(self.limits.get("token_budget", 24000))

    def cost_budget_usd(self) -> float:
        return float(self.limits.get("cost_budget_usd", 1.0))

    def timeout_seconds(self) -> float:
        return float(self.limits.get("timeout_seconds", 30))

    def denied_eval_tools(self) -> set[str]:
        return set(self.eval_policy.get("deny_tools", []))

    def action_config(self, action: str) -> dict[str, Any]:
        return self.actions.get(action) or {}

    def tool_config(self, tool: str) -> dict[str, Any]:
        return self.tools.get(tool) or {}
