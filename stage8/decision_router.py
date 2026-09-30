from __future__ import annotations

from typing import Any

from stage6.decision.base import DecisionEngine
from stage6.decision.schema import DecisionEngineUnavailable, DecisionResult, DecisionTask
from stage6.decision.rule import RuleDecisionEngine
from stage6.decision.zhipu import ZhipuDecisionEngine

try:
    from stage6.decision.jev import JevDecisionEngine
except ImportError:  # pragma: no cover
    JevDecisionEngine = None  # type: ignore[assignment]

from .schema import RouteResult


class OnlineDecisionRouter:
    """Stage8 在线决策门面。

    Stage6 的 DecisionEngine 负责产生原始选择；Stage8 在进入在线工作流前
    做一次轻量一致性校正：当模型返回的 choice 与其 probabilities 明显矛盾时，
    以合法候选集中的最高概率项为 effective choice，并记录 raw_choice。
    这不会改变 Stage6 benchmark 的原始结果，只影响在线执行结果。
    """

    def __init__(
        self,
        engine: DecisionEngine,
        *,
        fallback_engine: DecisionEngine | None = None,
        auto_threshold: float = 0.90,
        review_threshold: float = 0.70,
        fallback_on_error_only: bool = True,
        sanitize_result: bool = True,
    ):
        if not 0.0 <= review_threshold <= auto_threshold <= 1.0:
            raise ValueError("thresholds must satisfy 0 <= review <= auto <= 1")
        self.engine = engine
        self.fallback_engine = fallback_engine
        self.auto_threshold = auto_threshold
        self.review_threshold = review_threshold
        self.fallback_on_error_only = fallback_on_error_only
        self.sanitize_result = sanitize_result

    @property
    def engine_name(self) -> str:
        return self.engine.name

    def _route(self, confidence: float) -> str:
        if confidence >= self.auto_threshold:
            return "auto"
        if confidence >= self.review_threshold:
            return "review"
        return "fallback"

    @staticmethod
    def _sanitize(task: DecisionTask, result: DecisionResult) -> DecisionResult:
        probabilities = {
            str(key): float(value)
            for key, value in result.probabilities.items()
            if str(key) in task.options
        }
        if not probabilities:
            return result

        # 仅在概率分布可用时校正 choice；并采用 options 的稳定顺序解决平局。
        best_choice = max(task.options.keys(), key=lambda key: probabilities.get(key, 0.0))
        best_prob = probabilities.get(best_choice, 0.0)
        choice_prob = probabilities.get(result.choice, 0.0)
        raw_choice = result.choice
        corrected = choice_prob + 1e-9 < best_prob

        effective_choice = best_choice if corrected else result.choice
        # GLM 有时返回 confidence=0 但同时返回有效概率分布，在线层应至少保持
        # confidence 与实际分布一致，否则会把正确决策错误降级到 fallback。
        effective_confidence = max(float(result.confidence), best_prob)

        if not corrected and effective_confidence == float(result.confidence):
            return result

        metadata = dict(result.metadata)
        metadata.update(
            {
                "raw_choice": raw_choice,
                "effective_choice": effective_choice,
                "choice_corrected": corrected,
                "confidence_corrected": effective_confidence != float(result.confidence),
                "correction_source": "online_probability_consistency",
            }
        )
        return DecisionResult(
            engine=result.engine,
            task_id=result.task_id,
            task_type=result.task_type,
            choice=effective_choice,
            probabilities=dict(probabilities),
            confidence=effective_confidence,
            latency_ms=result.latency_ms,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            cost=result.cost,
            fallback=result.fallback,
            fallback_reason=result.fallback_reason,
            metadata=metadata,
        )

    def decide(self, task: DecisionTask, *, kind: str, alternatives: tuple[str, ...] = ()) -> RouteResult:
        fallback = False
        fallback_reason = ""
        engine = self.engine
        try:
            result = engine.decide(task)
        except (DecisionEngineUnavailable, TimeoutError, ConnectionError, RuntimeError) as exc:
            if not self.fallback_engine:
                raise
            engine = self.fallback_engine
            fallback = True
            fallback_reason = f"primary_engine_error:{type(exc).__name__}"
            result = engine.decide(task)

        raw_choice = result.choice
        if self.sanitize_result:
            result = self._sanitize(task, result)

        route = self._route(result.confidence)
        if not self.fallback_on_error_only and route == "fallback" and self.fallback_engine and engine is not self.fallback_engine:
            engine = self.fallback_engine
            fallback = True
            fallback_reason = "low_confidence_fallback"
            result = engine.decide(task)
            if self.sanitize_result:
                result = self._sanitize(task, result)
            route = self._route(result.confidence)

        reason = fallback_reason or f"confidence={result.confidence:.4f}"
        metadata = {**result.metadata, "probabilities": result.probabilities}
        if self.sanitize_result and raw_choice != result.choice:
            metadata["raw_choice"] = raw_choice
            metadata["effective_choice"] = result.choice

        return RouteResult(
            kind=kind,
            choice=result.choice,
            confidence=float(result.confidence),
            route=route,
            engine=result.engine,
            task_id=result.task_id,
            latency_ms=result.latency_ms,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            cost=result.cost,
            fallback=fallback,
            reason=reason,
            alternatives=alternatives,
            metadata=metadata,
        )


def build_decision_engine(name: str) -> DecisionEngine:
    name = name.lower()
    if name == "rule":
        return RuleDecisionEngine()
    if name == "glm":
        return ZhipuDecisionEngine()
    if name == "jev":
        if JevDecisionEngine is None:
            raise DecisionEngineUnavailable("stage6 JEV engine unavailable")
        return JevDecisionEngine()
    raise ValueError(f"unsupported decision engine: {name}")
