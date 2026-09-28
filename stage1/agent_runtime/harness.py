from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import asdict, dataclass, field, is_dataclass
import time
from collections.abc import Mapping
from typing import Any, Callable

from .trace import TraceRecorder, summarize
from .workflow import Workflow


class HarnessViolation(RuntimeError):
    pass


@dataclass
class HarnessContext:
    session_id: str
    stage: str = "INIT"
    step: int = 0
    followup_count: int = 0
    session_version: int = 0
    eval_mode: bool = False
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    deadline_at: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class Harness:
    def __init__(self, workflow: Workflow, tracer: TraceRecorder | None = None):
        self.workflow = workflow
        self.tracer = tracer or TraceRecorder()

    def _violate(self, ctx: HarnessContext, message: str, **extra: Any) -> None:
        self.tracer.record({
            "event": "harness_violation",
            "stage": ctx.stage,
            "step": ctx.step,
            "message": message,
            **extra,
        }, ctx.session_id)
        raise HarnessViolation(message)

    def _check_deadline(self, ctx: HarnessContext) -> None:
        if ctx.deadline_at is not None and time.monotonic() > ctx.deadline_at:
            self._violate(ctx, "会话已超过 deadline")

    def before(
        self,
        ctx: HarnessContext,
        agent: str,
        action: str,
        tool: str | None = None,
        *,
        expected_session_version: int | None = None,
        next_stage: str | None = None,
    ) -> None:
        self._check_deadline(ctx)
        if ctx.step >= self.workflow.max_steps():
            self._violate(ctx, "超过最大执行步数", max_steps=self.workflow.max_steps())
        if not self.workflow.is_agent_allowed(ctx.stage, agent):
            self._violate(ctx, f"阶段 {ctx.stage} 禁止 Agent={agent}")
        if not self.workflow.is_action_allowed(ctx.stage, action):
            self._violate(ctx, f"阶段 {ctx.stage} 禁止 action={action}")
        if not self.workflow.is_tool_allowed(ctx.stage, tool):
            self._violate(ctx, f"阶段 {ctx.stage} 禁止 tool={tool}")
        if ctx.eval_mode and tool in self.workflow.denied_eval_tools():
            self._violate(ctx, f"Eval 模式禁止工具={tool}")
        if expected_session_version is not None and expected_session_version != ctx.session_version:
            self._violate(
                ctx,
                f"session_version 冲突: expected={expected_session_version}, current={ctx.session_version}",
            )
        if action == "followup" and ctx.followup_count >= self.workflow.max_followup():
            self._violate(ctx, "超过最大追问次数", max_followup=self.workflow.max_followup())
        if next_stage is not None and next_stage != ctx.stage and not self.workflow.can_transition(ctx.stage, next_stage):
            self._violate(ctx, f"非法状态迁移: {ctx.stage} -> {next_stage}")

        self.tracer.record({
            "event": "before_action",
            "stage": ctx.stage,
            "agent": agent,
            "action": action,
            "tool": tool,
            "step": ctx.step + 1,
            "session_version": ctx.session_version,
            "eval_mode": ctx.eval_mode,
            "next_stage": next_stage,
        }, ctx.session_id)

    def consume_usage(
        self,
        ctx: HarnessContext,
        *,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost_usd: float = 0.0,
        source: str = "llm",
    ) -> None:
        token_total = max(0, int(input_tokens)) + max(0, int(output_tokens))
        if ctx.total_tokens + token_total > self.workflow.token_budget():
            self._violate(
                ctx,
                "超过 token budget",
                source=source,
                attempted_tokens=token_total,
                current_tokens=ctx.total_tokens,
                budget=self.workflow.token_budget(),
            )
        if ctx.total_cost_usd + float(cost_usd) > self.workflow.cost_budget_usd():
            self._violate(
                ctx,
                "超过 cost budget",
                source=source,
                attempted_cost_usd=cost_usd,
                current_cost_usd=ctx.total_cost_usd,
                budget_usd=self.workflow.cost_budget_usd(),
            )
        ctx.total_tokens += token_total
        ctx.total_cost_usd += float(cost_usd)
        self.tracer.record({
            "event": "usage",
            "source": source,
            "input_tokens": int(input_tokens),
            "output_tokens": int(output_tokens),
            "total_tokens": token_total,
            "cost_usd": float(cost_usd),
            "session_total_tokens": ctx.total_tokens,
            "session_total_cost_usd": round(ctx.total_cost_usd, 8),
        }, ctx.session_id)

    @staticmethod
    def _schema_view(result: Any) -> Any:
        if is_dataclass(result) and not isinstance(result, type):
            return asdict(result)
        if isinstance(result, Mapping):
            return dict(result)
        model_dump = getattr(result, "model_dump", None)
        if callable(model_dump):
            return model_dump()
        model_dict = getattr(result, "dict", None)
        if callable(model_dict):
            try:
                return model_dict()
            except TypeError:
                pass
        return result

    @staticmethod
    def _validate_result_schema(result: Any, schema: dict[str, Any] | None) -> None:
        if not schema:
            return
        value = Harness._schema_view(result)
        expected = schema.get("type")
        if expected == "object" and not isinstance(value, dict):
            raise HarnessViolation("action result 必须是 object")
        if expected == "array" and not isinstance(value, list):
            raise HarnessViolation("action result 必须是 array")
        if expected == "string" and not isinstance(value, str):
            raise HarnessViolation("action result 必须是 string")
        if expected == "boolean" and not isinstance(value, bool):
            raise HarnessViolation("action result 必须是 boolean")
        if expected == "integer" and (not isinstance(value, int) or isinstance(value, bool)):
            raise HarnessViolation("action result 必须是 integer")
        if expected == "number" and (not isinstance(value, (int, float)) or isinstance(value, bool)):
            raise HarnessViolation("action result 必须是 number")
        if isinstance(value, dict):
            for field in schema.get("required", []):
                if field not in value:
                    raise HarnessViolation(f"action result 缺少字段: {field}")
            for name, rule in (schema.get("properties") or {}).items():
                if name not in value:
                    continue
                typ = rule.get("type")
                field_value = value[name]
                if typ == "string" and not isinstance(field_value, str):
                    raise HarnessViolation(f"字段 {name} 必须是 string")
                if typ == "number" and (not isinstance(field_value, (int, float)) or isinstance(field_value, bool)):
                    raise HarnessViolation(f"字段 {name} 必须是 number")
                if typ == "integer" and (not isinstance(field_value, int) or isinstance(field_value, bool)):
                    raise HarnessViolation(f"字段 {name} 必须是 integer")
                if typ == "boolean" and not isinstance(field_value, bool):
                    raise HarnessViolation(f"字段 {name} 必须是 boolean")

    def _run_with_timeout(self, fn: Callable[[], Any], timeout: float) -> Any:
        executor = ThreadPoolExecutor(max_workers=1)
        future: Future[Any] = executor.submit(fn)
        try:
            result = future.result(timeout=float(timeout))
        except FutureTimeoutError as exc:
            future.cancel()
            executor.shutdown(wait=False, cancel_futures=True)
            raise exc
        except BaseException:
            executor.shutdown(wait=True, cancel_futures=True)
            raise
        else:
            executor.shutdown(wait=True, cancel_futures=True)
            return result

    def execute(
        self,
        ctx: HarnessContext,
        agent: str,
        action: str,
        fn: Callable[[], Any],
        tool: str | None = None,
        *,
        expected_session_version: int | None = None,
        next_stage: str | None = None,
    ) -> Any:
        self.before(ctx, agent, action, tool, expected_session_version=expected_session_version, next_stage=next_stage)
        action_stage = ctx.stage
        started = time.perf_counter()
        timeout = self.workflow.action_config(action).get("timeout_seconds", self.workflow.timeout_seconds())
        try:
            result = self._run_with_timeout(fn, float(timeout))
            self._validate_result_schema(result, self.workflow.action_config(action).get("result_schema"))
            ctx.step += 1
            ctx.session_version += 1
            if action == "followup":
                ctx.followup_count += 1
            if next_stage is not None:
                self.transition(ctx, next_stage)
            self.tracer.record({
                "event": "after_action",
                "stage": action_stage,
                "agent": agent,
                "action": action,
                "tool": tool,
                "status": "success",
                "step": ctx.step,
                "session_version": ctx.session_version,
                "result_stage": ctx.stage,
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                "output_summary": summarize(result),
            }, ctx.session_id)
            return result
        except FutureTimeoutError as exc:
            self.tracer.record({
                "event": "after_action",
                "stage": action_stage,
                "agent": agent,
                "action": action,
                "tool": tool,
                "status": "timeout",
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                "timeout_seconds": float(timeout),
            }, ctx.session_id)
            raise HarnessViolation(f"action 超时: {timeout}s") from exc
        except HarnessViolation:
            raise
        except Exception as exc:
            self.tracer.record({
                "event": "after_action",
                "stage": action_stage,
                "agent": agent,
                "action": action,
                "tool": tool,
                "status": "error",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            }, ctx.session_id)
            raise

    def transition(self, ctx: HarnessContext, dst: str) -> None:
        if ctx.stage == dst:
            return
        if not self.workflow.can_transition(ctx.stage, dst):
            self._violate(ctx, f"非法状态迁移: {ctx.stage} -> {dst}")
        old = ctx.stage
        ctx.stage = dst
        if old == "SCORING" and dst == "ASKING":
            ctx.followup_count = 0
            self.tracer.record({
                "event": "followup_reset",
                "reason": "new_main_question",
            }, ctx.session_id)
        self.tracer.record({
            "event": "transition",
            "from": old,
            "to": dst,
            "step": ctx.step,
            "session_version": ctx.session_version,
        }, ctx.session_id)
