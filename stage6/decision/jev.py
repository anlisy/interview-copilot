from __future__ import annotations

import json
import os
import random
import time
import urllib.error
import urllib.request
from types import SimpleNamespace
from typing import Any

from .base import DecisionEngine
from .schema import DecisionEngineUnavailable, DecisionResult, DecisionTask

try:  # Optional official SDK. The project does not require it.
    from typesafe_sdk import Choice, TypeSafeClient
except ImportError:  # pragma: no cover - optional dependency
    Choice = None  # type: ignore[assignment]
    TypeSafeClient = None  # type: ignore[assignment]


def _attr_or_key(value: Any, name: str, default: Any = None) -> Any:
    if hasattr(value, name):
        return getattr(value, name)
    if isinstance(value, dict):
        return value.get(name, default)
    return default


class _JevHttpClient:
    """Dependency-free client for TypeSafe System One."""

    def __init__(self, api_key: str, *, timeout: float = 30.0, max_attempts: int = 3) -> None:
        self.api_key = api_key
        self.timeout = timeout
        self.max_attempts = max_attempts

    def system_one(self, *, state: Any, questions: dict[str, Any], model: str) -> Any:
        payload = {"model": model, "state": state, "questions": questions}
        request = urllib.request.Request(
            os.getenv("JEV_API_URL", "https://api.typesafe.ai/v1/systemone"),
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        for attempt in range(1, self.max_attempts + 1):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                if exc.code not in (429, 529) or attempt >= self.max_attempts:
                    body = exc.read().decode("utf-8", errors="replace")
                    raise RuntimeError(f"JEV HTTP {exc.code}: {body[:500]}") from exc
            except (urllib.error.URLError, TimeoutError) as exc:
                if attempt >= self.max_attempts:
                    raise RuntimeError(f"JEV request failed: {exc}") from exc
            time.sleep((2 ** (attempt - 1)) + random.uniform(0.0, 0.25))
        raise RuntimeError("JEV request exhausted retries")


class JevDecisionEngine(DecisionEngine):
    """JEV Choice decision engine; official SDK is optional."""

    name = "jev"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        input_cost_per_million: float | None = None,
        output_cost_per_million: float | None = None,
        pricing_currency: str | None = None,
        client: Any | None = None,
        use_sdk: bool = True,
    ) -> None:
        key = api_key or os.getenv("TYPESAFE_API_KEY")
        self.model = model or os.getenv("JEV_MODEL", "jev-latest")
        self.input_cost_per_million = float(input_cost_per_million if input_cost_per_million is not None else os.getenv("JEV_INPUT_COST_PER_1M", "0.042"))
        self.output_cost_per_million = float(output_cost_per_million if output_cost_per_million is not None else os.getenv("JEV_OUTPUT_COST_PER_1M", "0"))
        self.pricing_currency = str(pricing_currency or os.getenv("JEV_PRICE_CURRENCY", "UNSPECIFIED")).strip() or "UNSPECIFIED"
        if client is not None:
            self.client = client
        elif use_sdk and TypeSafeClient is not None and Choice is not None:
            if key:
                os.environ.setdefault("TYPESAFE_API_KEY", key)
            self.client = TypeSafeClient()
        elif key:
            self.client = _JevHttpClient(key)
        else:
            raise DecisionEngineUnavailable("TYPESAFE_API_KEY is not set")

    def _decide(self, task: DecisionTask) -> DecisionResult:
        if len(task.options) > 255:
            raise ValueError("JEV Choice supports at most 255 options")
        start = time.perf_counter()
        if task.task_type == "intent":
            instructions = (
                "Determine whether question_a and question_b test the same underlying interview intent. "
                "Focus on the competency or intent being assessed, not merely shared keywords or topic words. "
                "Choose exactly one option and do not execute any action."
            )
        else:
            instructions = (
                "Choose exactly one option that best matches the task. "
                "Use the state as evidence, do not invent unavailable options, and do not execute any action."
            )
        if Choice is not None and TypeSafeClient is not None and isinstance(self.client, TypeSafeClient):
            question = Choice(
                instructions=instructions,
                criteria=dict(task.options),
            )
        else:
            question = {
                "type": "choice",
                "instructions": instructions,
                "criteria": dict(task.options),
            }
        response = self.client.system_one(state=task.state, questions={"decision": question}, model=self.model)
        if isinstance(response, dict):
            answer = response.get("answers", {}).get("decision")
            usage = response.get("usage", {})
        else:
            choices = getattr(response, "choices", {})
            answer = choices.get("decision") if isinstance(choices, dict) else _attr_or_key(choices, "decision")
            if answer is None:
                answers = getattr(response, "answers", {})
                answer = answers.get("decision") if isinstance(answers, dict) else None
            usage = getattr(response, "usage", {})
        if answer is None:
            raise ValueError("JEV response missing decision answer")

        choice = str(_attr_or_key(answer, "choice"))
        probabilities_raw = _attr_or_key(answer, "probabilities", {}) or {}
        probabilities = {str(k): float(v) for k, v in dict(probabilities_raw).items()}
        confidence = float(_attr_or_key(answer, "confidence", max(probabilities.values()) if probabilities else 0.0))
        input_tokens = int(_attr_or_key(usage, "input_tokens", 0) or 0)
        output_tokens = int(_attr_or_key(usage, "output_tokens", 0) or 0)
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
                "transport": "sdk" if TypeSafeClient is not None and isinstance(self.client, TypeSafeClient) else "urllib",
                "pricing_configured": bool(self.input_cost_per_million or self.output_cost_per_million),
                "input_cost_per_million": self.input_cost_per_million,
                "output_cost_per_million": self.output_cost_per_million,
                "pricing_currency": self.pricing_currency,
            },
        )
