from __future__ import annotations

import json
import os
import re
import time
from typing import Any

from .base import DecisionEngine
from .schema import DecisionEngineUnavailable, DecisionResult, DecisionTask

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - optional dependency in unit tests
    OpenAI = None  # type: ignore[assignment]


def _clean_json(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("model did not return a JSON object")
    return json.loads(text[start : end + 1])


class ZhipuDecisionEngine(DecisionEngine):
    """Use the existing Zhipu OpenAI-compatible endpoint for a bounded decision."""

    name = "glm"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        input_cost_per_million: float | None = None,
        output_cost_per_million: float | None = None,
        pricing_currency: str | None = None,
        timeout: float = 30.0,
        client: Any | None = None,
    ) -> None:
        if client is not None:
            self.client = client
        else:
            if OpenAI is None:
                raise DecisionEngineUnavailable("openai package is not installed")
            api_key = api_key or os.getenv("ZHIPU_API_KEY")
            if not api_key:
                raise DecisionEngineUnavailable("ZHIPU_API_KEY is not set")
            self.client = OpenAI(
                api_key=api_key,
                base_url=base_url or os.getenv("ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/paas/v4"),
                timeout=timeout,
            )
        self.model = model or os.getenv("ZHIPU_MODEL", "glm-4-flash")
        self.input_cost_per_million = float(
            input_cost_per_million if input_cost_per_million is not None else os.getenv("GLM_INPUT_COST_PER_1M", "0")
        )
        self.output_cost_per_million = float(
            output_cost_per_million if output_cost_per_million is not None else os.getenv("GLM_OUTPUT_COST_PER_1M", "0")
        )
        self.pricing_currency = str(pricing_currency or os.getenv("GLM_PRICE_CURRENCY", "CNY")).strip() or "CNY"

    def _decide(self, task: DecisionTask) -> DecisionResult:
        start = time.perf_counter()
        state = task.state if isinstance(task.state, str) else json.dumps(task.state, ensure_ascii=False)
        schema = {key: desc for key, desc in task.options.items()}
        prompt = (
            "你是一个有限候选集决策器。只允许从 options 中选择一个 choice。"
            "不要生成长文本，不要执行动作。返回严格 JSON："
            '{"choice":"...","probabilities":{"option":0.0},"confidence":0.0}.\n'
            f"task_type={task.task_type}\nstate={state}\noptions={json.dumps(schema, ensure_ascii=False)}"
        )
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你只做结构化有限选项判断。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
        raw_text = response.choices[0].message.content or "{}"
        payload = _clean_json(raw_text)
        usage = getattr(response, "usage", None)
        input_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        choice = str(payload["choice"])
        confidence_raw = payload.get("confidence")
        raw_probabilities = payload.get("probabilities") or {}
        probabilities = {str(k): float(v) for k, v in dict(raw_probabilities).items() if str(k) in task.options}
        probability_source = "model"
        if probabilities:
            total = sum(probabilities.values())
            if total <= 0:
                probabilities = {}
            else:
                probabilities = {key: value / total for key, value in probabilities.items()}
        if not probabilities:
            # Some GLM JSON responses return only choice/confidence. Keep the benchmark schema
            # valid without pretending we observed a model probability distribution.
            confidence = float(confidence_raw) if confidence_raw is not None else 1.0
            confidence = max(0.0, min(1.0, confidence))
            other_keys = [key for key in task.options if key != choice]
            probabilities = {key: 0.0 for key in task.options}
            probabilities[choice] = confidence
            remainder = max(0.0, 1.0 - confidence)
            if other_keys:
                share = remainder / len(other_keys)
                for key in other_keys:
                    probabilities[key] = share
            else:
                probabilities[choice] = 1.0
            probability_source = "derived_from_confidence"
        confidence = float(confidence_raw if confidence_raw is not None else max(probabilities.values()))
        cost = (input_tokens / 1_000_000) * self.input_cost_per_million + (output_tokens / 1_000_000) * self.output_cost_per_million
        return DecisionResult(
            engine=self.name,
            task_id=task.task_id,
            task_type=task.task_type,
            choice=choice,
            probabilities=probabilities,
            confidence=confidence,
            latency_ms=round((time.perf_counter() - start) * 1000, 3),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=round(cost, 8),
            metadata={
                "model": self.model,
                "probability_source": probability_source,
                "pricing_configured": bool(self.input_cost_per_million or self.output_cost_per_million),
                "input_cost_per_million": self.input_cost_per_million,
                "output_cost_per_million": self.output_cost_per_million,
                "pricing_currency": self.pricing_currency,
            },
        )
