from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable

from .harness import Harness, HarnessContext
from .trace import summarize
from .workflow import Workflow
from .zhipu_client import LLMResponse, ZhipuClient


class DecisionError(ValueError):
    pass


class Orchestrator:
    """中心 Agent：只规划下一动作；任何真实执行都必须经过 Harness。"""

    REQUIRED_DECISION_FIELDS = {"agent", "action", "session_version", "reason_code"}

    def __init__(
        self,
        workflow_path: str | Path,
        session_id: str,
        *,
        tracer=None,
        client: ZhipuClient | None = None,
        eval_mode: bool = False,
    ):
        self.workflow = Workflow.load(workflow_path)
        self.context = HarnessContext(session_id=session_id, eval_mode=eval_mode)
        self.harness = Harness(self.workflow, tracer=tracer)
        self.client = client
        self.prompt_path = Path(__file__).resolve().parents[1] / "prompts" / "orchestrator_router.txt"

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any]:
        raw = (text or "").strip()
        if raw.startswith("```"):
            parts = raw.split("```", 2)
            raw = parts[1] if len(parts) >= 2 else raw
            if raw.lstrip().startswith("json"):
                raw = raw.lstrip()[4:]
        try:
            data = json.loads(raw.strip())
        except json.JSONDecodeError:
            start, end = raw.find("{"), raw.rfind("}")
            if start < 0 or end <= start:
                raise DecisionError(f"LLM 没有返回合法 JSON: {text[:500]}")
            try:
                data = json.loads(raw[start:end + 1])
            except json.JSONDecodeError as exc:
                raise DecisionError(f"LLM JSON 解析失败: {text[:500]}") from exc
        if not isinstance(data, dict):
            raise DecisionError("编排决策必须是 JSON object")
        return data

    def _build_prompt(self, goal: str, observations: dict[str, Any]) -> str:
        stage = self.workflow.stage(self.context.stage)
        return self.prompt_path.read_text(encoding="utf-8").format(
            stage=self.context.stage,
            allowed_agents=stage.get("allowed_agents", []),
            allowed_actions=stage.get("allowed_actions", []),
            allowed_tools=stage.get("allowed_tools", []),
            session_version=self.context.session_version,
            step=self.context.step,
            followup_count=self.context.followup_count,
            goal=goal,
            observations=json.dumps(observations, ensure_ascii=False, default=str),
        )

    def _validate_decision(self, decision: dict[str, Any], stage: dict[str, Any]) -> tuple[str, str]:
        missing = self.REQUIRED_DECISION_FIELDS - set(decision)
        if missing:
            raise DecisionError(f"编排决策缺少字段: {sorted(missing)}")
        agent = decision.get("agent")
        action = decision.get("action")
        version = decision.get("session_version")
        reason_code = decision.get("reason_code")
        if not isinstance(agent, str) or not agent.strip():
            raise DecisionError("agent 必须是非空 string")
        if not isinstance(action, str) or not action.strip():
            raise DecisionError("action 必须是非空 string")
        if not isinstance(version, int) or isinstance(version, bool):
            raise DecisionError("session_version 必须是 integer")
        if version != self.context.session_version:
            raise DecisionError(
                f"模型返回的 session_version 已过期: expected={self.context.session_version}, got={version}"
            )
        if not isinstance(reason_code, str) or not reason_code.strip():
            raise DecisionError("reason_code 必须是非空 string")
        if agent not in stage.get("allowed_agents", []):
            raise DecisionError(f"模型选择了未授权 Agent={agent}")
        if action not in stage.get("allowed_actions", []):
            raise DecisionError(f"模型选择了未授权 action={action}")
        tool = decision.get("tool")
        if tool is not None and not isinstance(tool, str):
            raise DecisionError("tool 必须是 string")
        if tool is not None and not self.workflow.is_tool_allowed(self.context.stage, tool):
            raise DecisionError(f"模型选择了未授权 tool={tool}")
        if self.context.eval_mode and tool in self.workflow.denied_eval_tools():
            raise DecisionError(f"Eval 模式禁止 tool={tool}")
        return agent, action

    def decide(
        self,
        goal: str,
        observations: dict[str, Any],
        *,
        client: ZhipuClient | None = None,
    ) -> dict[str, Any]:
        client = client or self.client or ZhipuClient(timeout=self.workflow.timeout_seconds())
        prompt = self._build_prompt(goal, observations)
        stage = self.workflow.stage(self.context.stage)
        self.harness._check_deadline(self.context)

        remaining_tokens = self.workflow.token_budget() - self.context.total_tokens
        if remaining_tokens <= 0:
            self.harness._violate(self.context, "没有剩余 token budget")

        self.harness.tracer.record({
            "event": "agent_decision_request",
            "stage": self.context.stage,
            "agent": "orchestrator",
            "model": client.model,
            "step": self.context.step + 1,
            "session_version": self.context.session_version,
            "goal_summary": summarize(goal),
            "observations_summary": summarize(observations),
        }, self.context.session_id)

        response: LLMResponse = client.chat(
            [
                {"role": "system", "content": "你是 Interview Copilot 的中心编排器，只选择动作，不执行动作。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            top_p=0.7,
            max_tokens=256,
        )
        cost = self._estimate_cost(response.input_tokens, response.output_tokens, response.model)
        self.harness.consume_usage(
            self.context,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            cost_usd=cost,
            source="orchestrator",
        )

        try:
            decision = self._extract_json(response.content)
            agent, action = self._validate_decision(decision, stage)
        except DecisionError as exc:
            self.harness.tracer.record({
                "event": "agent_decision_rejected",
                "stage": self.context.stage,
                "agent": "orchestrator",
                "model": response.model,
                "error": str(exc),
            }, self.context.session_id)
            raise

        decision["model"] = response.model
        decision["usage"] = {
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "total_tokens": response.total_tokens,
            "cost_usd": cost,
        }
        decision["request_id"] = response.request_id
        self.harness.tracer.record({
            "event": "agent_decision_response",
            "stage": self.context.stage,
            "agent": "orchestrator",
            "model": response.model,
            "selected_agent": agent,
            "action": action,
            "decision_summary": summarize(decision),
        }, self.context.session_id)
        return decision

    @staticmethod
    def _estimate_cost(input_tokens: int, output_tokens: int, model: str) -> float:
        in_rate = float(os.getenv("ZHIPU_INPUT_USD_PER_1K", "0"))
        out_rate = float(os.getenv("ZHIPU_OUTPUT_USD_PER_1K", "0"))
        return (input_tokens / 1000.0) * in_rate + (output_tokens / 1000.0) * out_rate

    def run(
        self,
        decision: dict[str, Any],
        handlers: dict[str, Callable[[], Any]],
        tool: str | None = None,
        *,
        next_stage: str | None = None,
    ) -> Any:
        action = decision.get("action")
        agent = decision.get("agent")
        if not action or not agent:
            raise DecisionError("decision 缺少 agent/action")
        if action not in handlers:
            raise KeyError(f"未注册 action: {action}")
        expected_version = decision.get("session_version")
        if not isinstance(expected_version, int) or isinstance(expected_version, bool):
            raise DecisionError("decision.session_version 必须是 integer")
        return self.harness.execute(
            self.context,
            agent,
            action,
            handlers[action],
            tool=tool,
            expected_session_version=expected_version,
            next_stage=next_stage,
        )
