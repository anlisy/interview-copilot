from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Any, Mapping

from .permissions import TOOL_ACTION_MATRIX, TOOL_AGENT_MATRIX, TOOL_EVAL_DENY, TOOL_EVAL_ONLY, TOOL_RUNTIME_CONFIG
from .tool_models import JSON_TYPES, ToolSpec
from .tool_registry import ToolRegistry


class MCPRuntimeError(RuntimeError):
    pass


DEFAULT_AGENT_ACL = TOOL_AGENT_MATRIX


def _tool_input_schema(tool: Any) -> dict[str, Any]:
    for owner in (getattr(tool, "mcp_tool", None), tool):
        if owner is None:
            continue
        for name in ("inputSchema", "input_schema"):
            raw = getattr(owner, name, None)
            if isinstance(raw, dict):
                schema = raw.copy()
                schema.setdefault("type", "object")
                if schema.get("type") != "object":
                    raise MCPRuntimeError(f"MCP Tool={getattr(tool, 'name', '<unknown>')} inputSchema 必须是 object")
                return schema

    inputs = getattr(tool, "inputs", None)
    if isinstance(inputs, Mapping):
        props: dict[str, Any] = {}
        required: list[str] = []
        for name, raw_spec in inputs.items():
            spec = raw_spec if isinstance(raw_spec, Mapping) else {}
            prop = {k: v for k, v in spec.items() if k in {"type", "description", "enum", "items", "properties", "minimum", "maximum", "minLength", "maxLength"}}
            prop.setdefault("type", "string")
            props[str(name)] = prop
            if spec.get("required", True):
                required.append(str(name))
        return {"type": "object", "properties": props, "required": required, "additionalProperties": False}

    return {"type": "object", "additionalProperties": False}


def _tool_output_schema(tool: Any) -> dict[str, Any]:
    for owner in (getattr(tool, "mcp_tool", None), tool):
        if owner is None:
            continue
        for name in ("outputSchema", "output_schema"):
            raw = getattr(owner, name, None)
            if isinstance(raw, dict):
                schema = raw.copy()
                schema.setdefault("type", "object")
                if schema.get("type") in JSON_TYPES:
                    return schema
    return {"type": "object", "additionalProperties": True}


def _call_tool(tool: Any, arguments: dict[str, Any]) -> Any:
    if callable(tool):
        return tool(**arguments)
    forward = getattr(tool, "forward", None)
    if callable(forward):
        return forward(**arguments)
    raise TypeError(f"MCP Tool 不可调用: {getattr(tool, 'name', type(tool).__name__)}")


class MCPToolSession(AbstractContextManager[ToolRegistry]):
    """Own one MCP ToolCollection and expose only explicitly approved tools."""

    def __init__(
        self,
        server_parameters: dict[str, Any] | Any,
        *,
        allowed_tools: set[str] | frozenset[str] | None = None,
        agent_acl: Mapping[str, frozenset[str]] | None = None,
        tool_actions: Mapping[str, Mapping[str, frozenset[str]]] | None = None,
        eval_denied: set[str] | frozenset[str] = frozenset(),
        eval_only: set[str] | frozenset[str] = frozenset(),
        strict_allowlist: bool = True,
        trust_remote_code: bool = False,
    ) -> None:
        self.server_parameters = server_parameters
        self.allowed_tools = None if allowed_tools is None else set(allowed_tools)
        self.agent_acl = dict(agent_acl or DEFAULT_AGENT_ACL)
        self.tool_actions = {k: dict(v) for k, v in (tool_actions or {}).items()}
        self.eval_denied = frozenset(eval_denied)
        self.eval_only = frozenset(eval_only)
        self.strict_allowlist = strict_allowlist
        self.trust_remote_code = trust_remote_code
        self.collection: Any = None
        self.collection_cm: Any = None
        self.registry = ToolRegistry()
        self.discovered: tuple[str, ...] = ()
        self.skipped: tuple[str, ...] = ()

    def __enter__(self) -> ToolRegistry:
        if self.strict_allowlist and self.allowed_tools is None:
            raise MCPRuntimeError("strict_allowlist=True 时必须显式提供 allowed_tools")

        try:
            from smolagents import ToolCollection
        except Exception as exc:  # noqa: BLE001
            raise MCPRuntimeError('缺少 MCP 依赖，请安装: pip install "smolagents[mcp]==1.26.0"') from exc

        try:
            collection_cm = ToolCollection.from_mcp(
                self.server_parameters,
                trust_remote_code=self.trust_remote_code,
                structured_output=True,
            )
            self.collection_cm = collection_cm
            if hasattr(collection_cm, "__enter__") and hasattr(collection_cm, "__exit__"):
                self.collection = collection_cm.__enter__()
            else:
                # Backward/forward compatibility for adapters that may return
                # an already materialized ToolCollection rather than a context manager.
                self.collection = collection_cm
            tools = list(self.collection.tools)
            names = [str(getattr(t, "name", "")) for t in tools]
            self.discovered = tuple(sorted(n for n in names if n))

            if self.allowed_tools is not None:
                unknown = sorted(set(self.discovered) - self.allowed_tools)
                if unknown and self.strict_allowlist:
                    raise MCPRuntimeError(f"MCP Server 暴露了未获准 Tool: {unknown}")
                if unknown:
                    self.skipped = tuple(unknown)
                tools = [t for t in tools if getattr(t, "name", "") in self.allowed_tools]

            for tool in tools:
                name = str(getattr(tool, "name", "")).strip()
                if not name:
                    raise MCPRuntimeError("MCP Server 返回了没有 name 的 Tool")
                central_acl = frozenset(TOOL_AGENT_MATRIX.get(name, frozenset()))
                requested_acl = frozenset(self.agent_acl.get(name, central_acl))
                if central_acl and not requested_acl.issubset(central_acl):
                    raise MCPRuntimeError(f"Tool={name} 的 Agent ACL 不能扩大中央权限矩阵: {sorted(requested_acl - central_acl)}")
                acl = requested_acl
                if self.strict_allowlist and not acl:
                    raise MCPRuntimeError(f"已获准 Tool={name} 但未配置 Agent ACL")

                central_actions = {agent: frozenset(actions) for agent, actions in TOOL_ACTION_MATRIX.get(name, {}).items()}
                requested_actions = {agent: frozenset(actions) for agent, actions in self.tool_actions.get(name, central_actions).items()}
                for agent, actions in requested_actions.items():
                    if agent in central_actions and not actions.issubset(central_actions[agent]):
                        raise MCPRuntimeError(f"Tool={name} 的 Action ACL 不能扩大中央权限矩阵: Agent={agent}")
                    if agent not in acl:
                        raise MCPRuntimeError(f"Tool={name} 的 Action ACL 引用了无 Agent 权限主体: {agent}")
                if self.strict_allowlist and acl and not requested_actions:
                    if name in TOOL_ACTION_MATRIX:
                        requested_actions = central_actions

                eval_deny = name in TOOL_EVAL_DENY or name in self.eval_denied
                eval_only = name in TOOL_EVAL_ONLY or name in self.eval_only
                runtime_cfg = TOOL_RUNTIME_CONFIG.get(name, {"timeout_sec": 10.0, "retries": 0, "idempotent": True})
                spec = ToolSpec(
                    name=name,
                    description=str(getattr(tool, "description", "")),
                    input_schema=_tool_input_schema(tool),
                    output_schema=_tool_output_schema(tool),
                    allowed_agents=acl,
                    eval_deny=eval_deny,
                    eval_only=eval_only,
                    allowed_actions=requested_actions,
                    timeout_sec=float(runtime_cfg["timeout_sec"]),
                    retries=int(runtime_cfg["retries"]),
                    idempotent=bool(runtime_cfg["idempotent"]),
                    source="mcp:interview",
                    metadata={
                        "transport": self.server_parameters.get("transport", "stdio") if isinstance(self.server_parameters, dict) else "stdio",
                        "central_permission_source": name in TOOL_AGENT_MATRIX,
                    },
                )
                self.registry.register(spec, lambda args, _tool=tool: _call_tool(_tool, args))
            return self.registry
        except Exception:
            self._close_collection()
            raise

    def _close_collection(self) -> None:
        if self.collection_cm is not None and hasattr(self.collection_cm, "__exit__"):
            try:
                self.collection_cm.__exit__(None, None, None)
            finally:
                self.collection_cm = None
                self.collection = None
        else:
            self.collection = None
            self.collection_cm = None

    def __exit__(self, exc_type, exc, tb) -> bool:
        self._close_collection()
        return False
