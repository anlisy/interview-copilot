from __future__ import annotations

from typing import Iterable

from .tool_models import ToolHandler, ToolSpec


class ToolRegistry:
    def __init__(self, specs: Iterable[ToolSpec] = ()) -> None:
        self._specs: dict[str, ToolSpec] = {}
        self._handlers: dict[str, ToolHandler] = {}
        for spec in specs:
            self.register(spec)

    def register(self, spec: ToolSpec, handler: ToolHandler | None = None) -> None:
        if spec.name in self._specs:
            raise ValueError(f"Tool 已存在: {spec.name}")
        self._specs[spec.name] = spec
        if handler is not None:
            self._handlers[spec.name] = handler

    def bind(self, tool_name: str, handler: ToolHandler) -> None:
        if tool_name not in self._specs:
            raise KeyError(tool_name)
        self._handlers[tool_name] = handler

    def get(self, tool_name: str) -> ToolSpec:
        try:
            return self._specs[tool_name]
        except KeyError as exc:
            raise KeyError(f"未知 Tool: {tool_name}") from exc

    def has_handler(self, tool_name: str) -> bool:
        return tool_name in self._handlers

    def missing_handlers(self, names: Iterable[str] | None = None) -> tuple[str, ...]:
        selected = self._specs.keys() if names is None else names
        return tuple(sorted(name for name in selected if name in self._specs and name not in self._handlers))

    def handler(self, tool_name: str) -> ToolHandler:
        try:
            return self._handlers[tool_name]
        except KeyError as exc:
            raise KeyError(f"Tool 尚未绑定 handler: {tool_name}") from exc

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._specs))

    def export_metadata(self, names: Iterable[str] | None = None) -> list[dict]:
        selected = sorted(names) if names is not None else sorted(self._specs)
        return [
            {
                "name": s.name,
                "description": s.description,
                "input_schema": s.input_schema,
                "output_schema": s.output_schema,
                "allowed_agents": sorted(s.allowed_agents),
                "eval_deny": s.eval_deny,
                "eval_only": s.eval_only,
                "allowed_actions": {k: sorted(v) for k, v in s.allowed_actions.items()},
                "timeout_sec": s.timeout_sec,
                "retries": s.retries,
                "idempotent": s.idempotent,
                "source": s.source,
                "bound": name in self._handlers,
                "metadata": s.metadata,
            }
            for name, s in ((n, self.get(n)) for n in selected)
        ]
