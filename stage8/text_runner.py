from __future__ import annotations

import os
import time
from typing import Any

from .schema import AgentTextResult

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None  # type: ignore[assignment]


class ZhipuTextRunner:
    """真正的回答生成仍使用智谱 GLM，不与 Stage6 决策模型混用。"""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        input_cost_per_million: float | None = None,
        output_cost_per_million: float | None = None,
        timeout: float = 30.0,
        client: Any | None = None,
    ):
        if client is not None:
            self.client = client
        else:
            if OpenAI is None:
                raise RuntimeError("openai package is not installed")
            key = api_key or os.getenv("ZHIPU_API_KEY")
            if not key:
                raise RuntimeError("ZHIPU_API_KEY is not set")
            self.client = OpenAI(
                api_key=key,
                base_url=base_url or os.getenv("ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/paas/v4"),
                timeout=timeout,
            )
        self.model = model or os.getenv("ZHIPU_MODEL", "glm-4-flash")
        self.input_cost_per_million = float(input_cost_per_million if input_cost_per_million is not None else os.getenv("GLM_INPUT_COST_PER_1M", "0"))
        self.output_cost_per_million = float(output_cost_per_million if output_cost_per_million is not None else os.getenv("GLM_OUTPUT_COST_PER_1M", "0"))

    def run(self, context: str, *, skill: str = "", tool: str = "none", task: str = "") -> AgentTextResult:
        started = time.perf_counter()
        system = (
            "你是 Interview Copilot 的在线面试 Agent。"
            "遵守当前工作流、Skill 和工具权限；不要声称调用了未执行的工具；"
            "回答只基于上下文和当前任务。"
        )
        prompt = (
            f"当前 Skill: {skill or '未激活'}\n"
            f"允许/选定 Tool: {tool}\n"
            f"当前任务: {task}\n\n"
            f"受控上下文:\n{context}\n\n"
            "请直接完成当前面试任务。"
        )
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            temperature=0.2,
        )
        text = response.choices[0].message.content or ""
        usage = getattr(response, "usage", None)
        input_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        cost = (input_tokens / 1_000_000) * self.input_cost_per_million + (output_tokens / 1_000_000) * self.output_cost_per_million
        return AgentTextResult(
            text=text,
            engine="glm",
            latency_ms=round((time.perf_counter() - started) * 1000, 3),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=round(cost, 8),
            metadata={
                "model": self.model,
                "pricing_configured": bool(self.input_cost_per_million or self.output_cost_per_million),
            },
        )


class EchoTextRunner:
    """无网络 smoke runner；只用于本地集成测试，不代表生产回答路径。"""

    def run(self, context: str, *, skill: str = "", tool: str = "none", task: str = "") -> AgentTextResult:
        return AgentTextResult(
            text=f"[echo] skill={skill or 'none'} tool={tool} task={task}",
            engine="echo",
            metadata={"smoke": True},
        )
