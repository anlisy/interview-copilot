from __future__ import annotations

import threading
import time
from dataclasses import asdict, dataclass
from typing import Any, Callable

from .schema import SchemaError, validate_json
from .tool_models import ToolCallContext, ToolResult
from .tool_policy import ToolPolicy
from .tool_registry import ToolRegistry


@dataclass(frozen=True)
class ToolAuditEvent:
    tool: str
    agent: str
    eval_mode: bool
    ok: bool
    error_code: str | None
    attempts: int
    latency_ms: int
    executed: bool


class ToolExecutor:
    def __init__(self, registry: ToolRegistry, policy: ToolPolicy | None = None, audit_sink: Callable[[dict[str, Any]], None] | None = None) -> None:
        self.registry = registry
        self.policy = policy or ToolPolicy()
        self.audit_sink = audit_sink

    def _audit(self, event: ToolAuditEvent) -> None:
        if self.audit_sink:
            self.audit_sink(asdict(event))

    @staticmethod
    def _run_with_timeout(handler, arguments, timeout: float):
        result_box: list[Any] = []
        error_box: list[BaseException] = []

        def runner():
            try:
                result_box.append(handler(arguments))
            except BaseException as exc:  # noqa: BLE001
                error_box.append(exc)

        thread = threading.Thread(target=runner, daemon=True)
        thread.start()
        thread.join(timeout)
        if thread.is_alive():
            raise TimeoutError(f"Tool 超时 {timeout:.3f}s")
        if error_box:
            raise error_box[0]
        return result_box[0] if result_box else None

    def _failure(self, tool_name: str, ctx: ToolCallContext, started: float, *, code: str, message: str, blocked: bool, attempts: int = 0, executed: bool = False) -> ToolResult:
        result = ToolResult(
            tool_name,
            False,
            error_code=code,
            error_message=message,
            attempts=attempts,
            latency_ms=int((time.perf_counter() - started) * 1000),
            blocked=blocked,
            executed=executed,
        )
        self._audit(ToolAuditEvent(tool_name, ctx.agent, ctx.eval_mode, False, code, attempts, result.latency_ms, executed))
        return result

    def call(self, tool_name: str, arguments: dict, ctx: ToolCallContext) -> ToolResult:
        started = time.perf_counter()
        try:
            spec = self.registry.get(tool_name)
        except KeyError as exc:
            return self._failure(tool_name, ctx, started, code="unknown_tool", message=str(exc), blocked=True)

        try:
            self.policy.check(spec, ctx)
        except PermissionError as exc:
            return self._failure(tool_name, ctx, started, code="policy_denied", message=str(exc), blocked=True)

        try:
            validate_json(arguments, spec.input_schema, allow_extra=False)
        except SchemaError as exc:
            return self._failure(tool_name, ctx, started, code="input_schema_invalid", message=str(exc), blocked=False)

        if not self.registry.has_handler(tool_name):
            return self._failure(
                tool_name,
                ctx,
                started,
                code="tool_unavailable",
                message=f"Tool={tool_name} 已获授权，但当前 Runtime 没有绑定可执行 handler；不会执行调用",
                blocked=False,
                executed=False,
            )

        try:
            handler = self.registry.handler(tool_name)
        except KeyError as exc:
            return self._failure(tool_name, ctx, started, code="tool_unavailable", message=str(exc), blocked=False, executed=False)

        attempts = 0
        max_attempts = 1 + (spec.retries if spec.idempotent else 0)
        timeout = spec.timeout_sec
        last_error: BaseException | None = None

        for _ in range(max_attempts):
            attempts += 1
            if ctx.deadline_ms is not None:
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                remaining_ms = ctx.deadline_ms - elapsed_ms
                if remaining_ms <= 0:
                    last_error = TimeoutError("Tool session deadline exceeded")
                    break
                timeout = min(spec.timeout_sec, max(0.001, remaining_ms / 1000.0))
            try:
                output = self._run_with_timeout(handler, arguments, timeout)
                validate_json(output, spec.output_schema, allow_extra=False)
                latency = int((time.perf_counter() - started) * 1000)
                result = ToolResult(tool_name, True, output=output, attempts=attempts, latency_ms=latency, executed=True)
                self._audit(ToolAuditEvent(tool_name, ctx.agent, ctx.eval_mode, True, None, attempts, latency, True))
                return result
            except TimeoutError as exc:
                last_error = exc
                break
            except SchemaError as exc:
                return self._failure(tool_name, ctx, started, code="output_schema_invalid", message=str(exc), blocked=False, attempts=attempts, executed=True)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                continue

        code = "timeout" if isinstance(last_error, TimeoutError) else "tool_error"
        return self._failure(tool_name, ctx, started, code=code, message=str(last_error) if last_error else "unknown tool error", blocked=False, attempts=attempts, executed=attempts > 0)
