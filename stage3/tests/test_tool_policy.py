from __future__ import annotations

import time

from stage3.agent_runtime.default_tools import build_default_registry
from stage3.agent_runtime.permissions import AGENT_TOOL_MATRIX, TOOL_ACTION_MATRIX
from stage3.agent_runtime.schema import SchemaError, validate_json
from stage3.agent_runtime.tool_executor import ToolExecutor
from stage3.agent_runtime.tool_models import ToolCallContext, ToolSpec
from stage3.agent_runtime.tool_policy import ToolPolicy
from stage3.agent_runtime.tool_registry import ToolRegistry


def test_agent_tool_matrix_is_explicit():
    registry = build_default_registry()
    assert set(AGENT_TOOL_MATRIX["interviewer"]) == {"local_rag", "nowcoder_search", "memory_search"}
    assert AGENT_TOOL_MATRIX["scorer"] == frozenset()
    assert AGENT_TOOL_MATRIX["reviewer"] == frozenset({"memory_search"})
    assert AGENT_TOOL_MATRIX["evaluation_harness"] == frozenset({"ground_truth_search"})
    assert set(registry.get("memory_search").allowed_agents) == {"interviewer", "reviewer"}


def test_interviewer_permissions_and_actions():
    registry = build_default_registry()
    policy = ToolPolicy()
    assert policy.decide(registry.get("local_rag"), ToolCallContext("interviewer", action="generate")).allowed
    assert policy.decide(registry.get("local_rag"), ToolCallContext("interviewer", action="followup")).allowed
    assert not policy.decide(registry.get("nowcoder_search"), ToolCallContext("interviewer", action="diagnose")).allowed
    assert policy.decide(registry.get("nowcoder_search"), ToolCallContext("interviewer", action="generate")).allowed
    assert policy.decide(registry.get("memory_search"), ToolCallContext("interviewer", action="followup")).allowed


def test_scorer_has_no_external_tool_permissions():
    registry = build_default_registry()
    policy = ToolPolicy()
    for name in registry.names():
        assert not policy.decide(registry.get(name), ToolCallContext("scorer", action="score")).allowed


def test_reviewer_only_memory_search_for_review():
    registry = build_default_registry()
    policy = ToolPolicy()
    assert policy.decide(registry.get("memory_search"), ToolCallContext("reviewer", action="review")).allowed
    assert not policy.decide(registry.get("memory_search"), ToolCallContext("reviewer", action="generate")).allowed
    assert not policy.decide(registry.get("local_rag"), ToolCallContext("reviewer", action="review")).allowed


def test_eval_harness_is_only_ground_truth_principal():
    registry = build_default_registry()
    policy = ToolPolicy()
    gt = registry.get("ground_truth_search")
    assert policy.decide(gt, ToolCallContext("interviewer", eval_mode=True)).reason_code == "eval_only_denied"
    assert policy.decide(gt, ToolCallContext("evaluation_harness", eval_mode=False, principal_type="evaluator")).reason_code == "eval_only_denied"
    assert policy.decide(
        gt,
        ToolCallContext("evaluation_harness", eval_mode=True, action="retrieve_ground_truth", principal_type="evaluator"),
    ).allowed
    assert not policy.decide(gt, ToolCallContext("evaluation_harness", eval_mode=True, action="generate", principal_type="evaluator")).allowed


def test_eval_denies_nowcoder_but_keeps_allowed_rag_and_memory():
    registry = build_default_registry()
    policy = ToolPolicy()
    assert policy.decide(registry.get("local_rag"), ToolCallContext("interviewer", True, action="generate")).allowed
    assert policy.decide(registry.get("memory_search"), ToolCallContext("interviewer", True, action="followup")).allowed
    assert not policy.decide(registry.get("nowcoder_search"), ToolCallContext("interviewer", True, action="generate")).allowed


def test_visible_tools_match_permissions():
    registry = build_default_registry()
    policy = ToolPolicy()
    assert policy.visible_tools(registry, ToolCallContext("interviewer", action="generate")) == (
        "local_rag", "memory_search", "nowcoder_search",
    )
    assert policy.visible_tools(registry, ToolCallContext("interviewer", eval_mode=True, action="generate")) == (
        "local_rag", "memory_search",
    )
    assert policy.visible_tools(registry, ToolCallContext("scorer", action="score")) == ()
    assert policy.visible_tools(registry, ToolCallContext("reviewer", action="review")) == ("memory_search",)
    assert policy.visible_tools(
        registry,
        ToolCallContext("evaluation_harness", eval_mode=True, action="retrieve_ground_truth", principal_type="evaluator"),
    ) == ("ground_truth_search",)


def test_unknown_agent_and_principal_fail_closed():
    registry = build_default_registry()
    policy = ToolPolicy()
    assert not policy.decide(registry.get("memory_search"), ToolCallContext("unknown", action="generate")).allowed
    assert not policy.decide(registry.get("memory_search"), ToolCallContext("interviewer", action="generate", principal_type="robot")).allowed


def test_input_schema_and_output_schema():
    validate_json({"q": "x"}, {"type": "object", "properties": {"q": {"type": "string"}}})
    with_schema_error = False
    try:
        validate_json({"q": 1}, {"type": "object", "properties": {"q": {"type": "string"}}})
    except SchemaError:
        with_schema_error = True
    assert with_schema_error


def test_schema_supports_common_json_constraints():
    validate_json("abc", {"type": "string", "minLength": 2, "maxLength": 4})
    validate_json(3, {"type": ["integer", "number"], "minimum": 1, "maximum": 5})
    validate_json(None, {"type": "null"})
    validate_json({"mode": "a"}, {"type": "object", "properties": {"mode": {"type": "string", "enum": ["a", "b"]}}})
    try:
        validate_json({"mode": "c"}, {"type": "object", "properties": {"mode": {"type": "string", "enum": ["a", "b"]}}})
    except SchemaError:
        pass
    else:
        raise AssertionError("enum should fail")


def test_executor_success_and_metadata():
    spec = ToolSpec("echo", "echo", {"type": "object", "required": ["q"]}, {"type": "object", "required": ["answer"]}, allowed_agents=frozenset({"interviewer"}))
    registry = ToolRegistry([spec])
    registry.bind("echo", lambda args: {"answer": args["q"]})
    result = ToolExecutor(registry).call("echo", {"q": "hi"}, ToolCallContext("interviewer"))
    assert result.ok is True
    assert result.output["answer"] == "hi"
    assert result.attempts == 1


def test_executor_blocks_before_handler():
    called = []
    spec = ToolSpec("blocked", "blocked", {"type": "object"}, {"type": "object"}, allowed_agents=frozenset({"scorer"}))
    registry = ToolRegistry([spec])
    registry.bind("blocked", lambda args: called.append(1) or {})
    result = ToolExecutor(registry).call("blocked", {}, ToolCallContext("interviewer"))
    assert not result.ok
    assert result.blocked
    assert called == []


def test_executor_action_policy_blocks_before_handler():
    called = []
    spec = ToolSpec(
        "action_tool", "action", {"type": "object"}, {"type": "object"},
        allowed_agents=frozenset({"interviewer"}),
        allowed_actions={"interviewer": frozenset({"generate"})},
    )
    registry = ToolRegistry([spec])
    registry.bind("action_tool", lambda args: called.append(1) or {})
    result = ToolExecutor(registry).call("action_tool", {}, ToolCallContext("interviewer", action="score"))
    assert not result.ok
    assert result.blocked
    assert called == []


def test_executor_timeout():
    spec = ToolSpec("slow", "slow", {"type": "object"}, {"type": "object"}, allowed_agents=frozenset({"interviewer"}), timeout_sec=0.05)
    registry = ToolRegistry([spec])
    registry.bind("slow", lambda args: (time.sleep(0.2), {})[1])
    result = ToolExecutor(registry).call("slow", {}, ToolCallContext("interviewer"))
    assert not result.ok
    assert result.error_code == "timeout"


def test_non_idempotent_tool_is_not_retried():
    calls = []
    spec = ToolSpec("once", "once", {"type": "object"}, {"type": "object"}, allowed_agents=frozenset({"interviewer"}), retries=2, idempotent=False)
    registry = ToolRegistry([spec])
    registry.bind("once", lambda _: calls.append(1) or (_ for _ in ()).throw(RuntimeError("boom")))
    result = ToolExecutor(registry).call("once", {}, ToolCallContext("interviewer"))
    assert not result.ok
    assert result.attempts == 1
    assert len(calls) == 1


def test_idempotent_tool_can_retry():
    calls = []
    spec = ToolSpec("retry", "retry", {"type": "object"}, {"type": "object", "required": ["ok"]}, allowed_agents=frozenset({"interviewer"}), retries=1, idempotent=True)
    registry = ToolRegistry([spec])

    def handler(_):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("temporary")
        return {"ok": True}

    registry.bind("retry", handler)
    result = ToolExecutor(registry).call("retry", {}, ToolCallContext("interviewer"))
    assert result.ok
    assert result.attempts == 2


def test_unknown_tool_fails_closed():
    registry = build_default_registry()
    result = ToolExecutor(registry).call("not_exists", {}, ToolCallContext("interviewer"))
    assert not result.ok
    assert result.error_code == "unknown_tool"
    assert result.blocked


def test_executor_rejects_extra_input_when_schema_forbids():
    spec = ToolSpec("strict", "strict", {"type": "object", "properties": {"q": {"type": "string"}}, "additionalProperties": False}, {"type": "object"}, allowed_agents=frozenset({"interviewer"}))
    registry = ToolRegistry([spec])
    registry.bind("strict", lambda args: {})
    result = ToolExecutor(registry).call("strict", {"q": "x", "evil": 1}, ToolCallContext("interviewer"))
    assert not result.ok
    assert result.error_code == "input_schema_invalid"


def test_audit_sink_receives_success_and_denial():
    events = []
    registry = build_default_registry()
    executor = ToolExecutor(registry, audit_sink=events.append)
    executor.call("memory_search", {}, ToolCallContext("interviewer"))
    executor.call("nowcoder_search", {}, ToolCallContext("interviewer", eval_mode=True))
    assert len(events) == 2
    assert events[0]["tool"] == "memory_search"
    assert events[0]["ok"] is False
    assert events[1]["error_code"] == "policy_denied"


def test_registry_rejects_duplicate_tool():
    spec = ToolSpec("dup", "dup", {"type": "object"}, {"type": "object"}, allowed_agents=frozenset({"interviewer"}))
    registry = ToolRegistry([spec])
    try:
        registry.register(spec)
    except ValueError as exc:
        assert "Tool 已存在" in str(exc)
    else:
        raise AssertionError("duplicate tool should fail")


def test_mcp_loader_enables_structured_output(monkeypatch):
    import sys
    import types
    from stage3.agent_runtime.mcp_loader import load_mcp_tools

    calls = {}

    class Collection:
        def __init__(self): self.tools = ["t1"]
        def __enter__(self): return self
        def __exit__(self, *args): return False

    class ToolCollection:
        @staticmethod
        def from_mcp(config, **kwargs):
            calls["config"] = config
            calls.update(kwargs)
            return Collection()

    monkeypatch.setitem(sys.modules, "smolagents", types.SimpleNamespace(ToolCollection=ToolCollection))
    with load_mcp_tools({"url": "http://example/mcp", "transport": "streamable-http"}) as tools:
        assert tools == ["t1"]
    assert calls["structured_output"] is True
    assert calls["trust_remote_code"] is False


def test_mcp_runtime_requires_explicit_allowlist_in_strict_mode(monkeypatch):
    import sys, types
    from stage3.agent_runtime.mcp_runtime import MCPRuntimeError, MCPToolSession

    class ToolCollection:
        @staticmethod
        def from_mcp(config, **kwargs):
            raise AssertionError("should not connect without allowlist")

    monkeypatch.setitem(sys.modules, "smolagents", types.SimpleNamespace(ToolCollection=ToolCollection))
    try:
        with MCPToolSession({"command": "python"}, strict_allowlist=True):
            pass
    except MCPRuntimeError as exc:
        assert "必须显式提供 allowed_tools" in str(exc)
    else:
        raise AssertionError("strict MCP session must require allowlist")


def test_mcp_runtime_maps_discovered_tool_with_explicit_acl(monkeypatch):
    import sys, types
    from stage3.agent_runtime.mcp_runtime import MCPToolSession

    class FakeTool:
        name = "mcp_echo"
        description = "echo"
        inputs = {"text": {"type": "string", "description": "text"}}
        output_schema = {"type": "object", "properties": {"echo": {"type": "string"}, "length": {"type": "integer"}}, "required": ["echo", "length"]}
        def __call__(self, **kwargs): return {"echo": kwargs["text"], "length": len(kwargs["text"])}

    class Collection:
        tools = [FakeTool()]
        def __enter__(self): return self
        def __exit__(self, *args): return False

    class ToolCollection:
        @staticmethod
        def from_mcp(config, **kwargs):
            assert kwargs["structured_output"] is True
            assert kwargs["trust_remote_code"] is False
            return Collection()

    monkeypatch.setitem(sys.modules, "smolagents", types.SimpleNamespace(ToolCollection=ToolCollection))
    with MCPToolSession(
        {"command": "python"},
        allowed_tools={"mcp_echo"},
        agent_acl={"mcp_echo": frozenset({"interviewer"})},
        tool_actions={"mcp_echo": {"interviewer": frozenset({"generate"})}},
    ) as registry:
        result = ToolExecutor(registry).call("mcp_echo", {"text": "abc"}, ToolCallContext("interviewer", action="generate"))
        assert result.ok
        assert result.output == {"echo": "abc", "length": 3}


def test_mcp_runtime_rejects_unapproved_discovered_tool(monkeypatch):
    import sys, types
    from stage3.agent_runtime.mcp_runtime import MCPRuntimeError, MCPToolSession

    class FakeTool:
        name = "unexpected"
        description = "unexpected"
        inputs = {}
        output_schema = {"type": "object"}

    class Collection:
        tools = [FakeTool()]
        def __enter__(self): return self
        def __exit__(self, *args): return False

    class ToolCollection:
        @staticmethod
        def from_mcp(config, **kwargs): return Collection()

    monkeypatch.setitem(sys.modules, "smolagents", types.SimpleNamespace(ToolCollection=ToolCollection))
    try:
        with MCPToolSession({"command": "python"}, allowed_tools={"mcp_echo"}):
            pass
    except MCPRuntimeError as exc:
        assert "未获准 Tool" in str(exc)
    else:
        raise AssertionError("unapproved MCP tool must fail closed")


def test_mcp_runtime_rejects_allowlisted_tool_without_acl(monkeypatch):
    import sys, types
    from stage3.agent_runtime.mcp_runtime import MCPRuntimeError, MCPToolSession

    class FakeTool:
        name = "mcp_echo"
        description = "echo"
        inputs = {"text": {"type": "string"}}
        output_schema = {"type": "object"}

    class Collection:
        tools = [FakeTool()]
        def __enter__(self): return self
        def __exit__(self, *args): return False

    class ToolCollection:
        @staticmethod
        def from_mcp(config, **kwargs): return Collection()

    monkeypatch.setitem(sys.modules, "smolagents", types.SimpleNamespace(ToolCollection=ToolCollection))
    try:
        with MCPToolSession({"command": "python"}, allowed_tools={"mcp_echo"}):
            pass
    except MCPRuntimeError as exc:
        assert "未配置 Agent ACL" in str(exc)
    else:
        raise AssertionError("allowlisted tool without ACL must fail closed")


def test_mcp_runtime_non_strict_mode_skips_unapproved_and_blocks_missing_acl(monkeypatch):
    import sys, types
    from stage3.agent_runtime.mcp_runtime import MCPToolSession

    class A:
        name = "mcp_echo"
        description = "echo"
        inputs = {"text": {"type": "string"}}
        output_schema = {"type": "object"}
        def __call__(self, **kwargs): return {}
    class B:
        name = "unexpected"
        description = "x"
        inputs = {}
        output_schema = {"type": "object"}
    class Collection:
        tools = [A(), B()]
        def __enter__(self): return self
        def __exit__(self, *args): return False
    class ToolCollection:
        @staticmethod
        def from_mcp(config, **kwargs): return Collection()
    monkeypatch.setitem(sys.modules, "smolagents", types.SimpleNamespace(ToolCollection=ToolCollection))
    with MCPToolSession({"command": "python"}, allowed_tools={"mcp_echo"}, strict_allowlist=False) as registry:
        assert registry.names() == ("mcp_echo",)
        result = ToolExecutor(registry).call("mcp_echo", {"text": "x"}, ToolCallContext("interviewer"))
        assert result.error_code == "policy_denied" or result.error_code == "handler_missing"


def test_mcp_output_schema_accepts_scalar_and_array(monkeypatch):
    import sys, types
    from stage3.agent_runtime.mcp_runtime import MCPToolSession

    class ScalarTool:
        name = "scalar"
        description = "scalar"
        inputs = {"q": {"type": "string"}}
        output_schema = {"type": "string"}
        def __call__(self, **kwargs): return kwargs["q"]
    class ArrayTool:
        name = "array"
        description = "array"
        inputs = {"q": {"type": "string"}}
        output_schema = {"type": "array", "items": {"type": "string"}}
        def __call__(self, **kwargs): return [kwargs["q"]]
    class Collection:
        tools = [ScalarTool(), ArrayTool()]
        def __enter__(self): return self
        def __exit__(self, *args): return False
    class ToolCollection:
        @staticmethod
        def from_mcp(config, **kwargs): return Collection()
    monkeypatch.setitem(sys.modules, "smolagents", types.SimpleNamespace(ToolCollection=ToolCollection))
    with MCPToolSession(
        {"command": "python"},
        allowed_tools={"scalar", "array"},
        agent_acl={"scalar": frozenset({"interviewer"}), "array": frozenset({"interviewer"})},
    ) as registry:
        assert ToolExecutor(registry).call("scalar", {"q": "x"}, ToolCallContext("interviewer")).output == "x"
        assert ToolExecutor(registry).call("array", {"q": "x"}, ToolCallContext("interviewer")).output == ["x"]


def test_agent_tool_and_tool_agent_matrices_are_consistent():
    from stage3.agent_runtime.permissions import TOOL_AGENT_MATRIX
    for agent, tools in AGENT_TOOL_MATRIX.items():
        for tool in tools:
            assert agent in TOOL_AGENT_MATRIX[tool]
    for tool, agents in TOOL_AGENT_MATRIX.items():
        for agent in agents:
            assert tool in AGENT_TOOL_MATRIX[agent]


def test_mcp_runtime_uses_central_action_matrix_when_not_explicitly_repeated(monkeypatch):
    import sys, types
    from stage3.agent_runtime.mcp_runtime import MCPToolSession

    class FakeTool:
        name = "nowcoder_search"
        description = "search"
        inputs = {"query": {"type": "string"}}
        output_schema = {"type": "object", "properties": {"items": {"type": "array"}}, "required": ["items"]}
        def __call__(self, **kwargs): return {"items": []}

    class Collection:
        tools = [FakeTool()]
        def __enter__(self): return self
        def __exit__(self, *args): return False

    class ToolCollection:
        @staticmethod
        def from_mcp(config, **kwargs): return Collection()

    monkeypatch.setitem(sys.modules, "smolagents", types.SimpleNamespace(ToolCollection=ToolCollection))
    with MCPToolSession(
        {"command": "python"},
        allowed_tools={"nowcoder_search"},
        agent_acl={"nowcoder_search": frozenset({"interviewer"})},
    ) as registry:
        executor = ToolExecutor(registry)
        assert executor.call("nowcoder_search", {"query": "x"}, ToolCallContext("interviewer", action="generate")).ok
        denied = executor.call("nowcoder_search", {"query": "x"}, ToolCallContext("interviewer", action="diagnose"))
        assert not denied.ok
        assert denied.error_code == "policy_denied"


def test_registry_metadata_exposes_permission_contract():
    registry = build_default_registry()
    rows = {x["name"]: x for x in registry.export_metadata()}
    assert rows["nowcoder_search"]["allowed_actions"] == {"interviewer": ["generate"]}
    assert rows["ground_truth_search"]["eval_only"] is True
    assert rows["ground_truth_search"]["allowed_agents"] == ["evaluation_harness"]


def test_default_registry_allowed_tool_without_mcp_handler_is_not_executed():
    registry = build_default_registry()
    result = ToolExecutor(registry).call(
        "nowcoder_search",
        {"query": "x", "limit": 1},
        ToolCallContext("interviewer", action="generate"),
    )
    assert not result.ok
    assert result.error_code == "tool_unavailable"
    assert result.executed is False
    assert result.attempts == 0


def test_action_acl_is_required_when_action_is_present():
    spec = ToolSpec(
        "no_action_contract", "x", {"type": "object"}, {"type": "object"},
        allowed_agents=frozenset({"interviewer"}),
    )
    registry = ToolRegistry([spec])
    registry.bind("no_action_contract", lambda _: {})
    result = ToolExecutor(registry).call(
        "no_action_contract", {}, ToolCallContext("interviewer", action="generate")
    )
    assert not result.ok
    assert result.error_code == "policy_denied"
    assert result.executed is False


def test_default_registry_has_no_handlers_but_mcp_registry_can_bind():
    registry = build_default_registry()
    assert registry.missing_handlers() == (
        "ground_truth_search", "local_rag", "memory_search", "nowcoder_search"
    )


def test_central_eval_rules_are_applied_to_mcp_known_tool(monkeypatch):
    import sys, types
    from stage3.agent_runtime.mcp_runtime import MCPToolSession

    class FakeTool:
        name = "nowcoder_search"
        description = "search"
        inputs = {"query": {"type": "string"}, "limit": {"type": "integer"}}
        output_schema = {"type": "object", "properties": {"items": {"type": "array"}}, "required": ["items"]}
        def __call__(self, **kwargs):
            return {"items": [{"query": kwargs["query"]}]}

    class Collection:
        tools = [FakeTool()]
        def __enter__(self): return self
        def __exit__(self, *args): return False

    class ToolCollection:
        @staticmethod
        def from_mcp(config, **kwargs): return Collection()

    monkeypatch.setitem(sys.modules, "smolagents", types.SimpleNamespace(ToolCollection=ToolCollection))
    with MCPToolSession(
        {"command": "python"},
        allowed_tools={"nowcoder_search"},
        strict_allowlist=True,
    ) as registry:
        policy = ToolPolicy()
        denied = policy.decide(registry.get("nowcoder_search"), ToolCallContext("interviewer", eval_mode=True, action="generate"))
        assert not denied.allowed
        assert denied.reason_code == "eval_tool_denied"


def test_mcp_known_tool_cannot_expand_central_agent_acl(monkeypatch):
    import sys, types
    from stage3.agent_runtime.mcp_runtime import MCPRuntimeError, MCPToolSession

    class FakeTool:
        name = "nowcoder_search"
        description = "search"
        inputs = {"query": {"type": "string"}}
        output_schema = {"type": "object", "properties": {"items": {"type": "array"}}, "required": ["items"]}

    class Collection:
        tools = [FakeTool()]
        def __enter__(self): return self
        def __exit__(self, *args): return False

    class ToolCollection:
        @staticmethod
        def from_mcp(config, **kwargs): return Collection()

    monkeypatch.setitem(sys.modules, "smolagents", types.SimpleNamespace(ToolCollection=ToolCollection))
    try:
        with MCPToolSession(
            {"command": "python"},
            allowed_tools={"nowcoder_search"},
            agent_acl={"nowcoder_search": frozenset({"interviewer", "reviewer"})},
        ):
            pass
    except MCPRuntimeError as exc:
        assert "不能扩大中央权限矩阵" in str(exc)
    else:
        raise AssertionError("MCP adapter must not widen central ACL")


def test_mcp_from_mcp_context_manager_is_entered_before_tools_access(monkeypatch):
    import sys, types
    from contextlib import contextmanager
    from stage3.agent_runtime.mcp_runtime import MCPToolSession

    class FakeTool:
        name = "mcp_echo"
        description = "echo"
        inputs = {"text": {"type": "string"}}
        output_schema = {"type": "object", "properties": {"echo": {"type": "string"}}, "required": ["echo"]}

        def __call__(self, **kwargs):
            return {"echo": kwargs["text"]}

    class Collection:
        tools = [FakeTool()]

    entered = []

    @contextmanager
    def fake_from_mcp(config, **kwargs):
        entered.append((config, kwargs))
        yield Collection()

    monkeypatch.setitem(sys.modules, "smolagents", types.SimpleNamespace(
        ToolCollection=types.SimpleNamespace(from_mcp=staticmethod(fake_from_mcp))
    ))

    with MCPToolSession(
        {"command": "python"},
        allowed_tools={"mcp_echo"},
        agent_acl={"mcp_echo": frozenset({"interviewer"})},
        tool_actions={"mcp_echo": {"interviewer": frozenset({"generate"})}},
    ) as registry:
        assert registry.names() == ("mcp_echo",)
        assert registry.has_handler("mcp_echo")

    assert len(entered) == 1
    assert entered[0][1]["structured_output"] is True
    assert entered[0][1]["trust_remote_code"] is False


def test_stdio_mcp_clients_use_stdio_server_parameters():
    try:
        from mcp import StdioServerParameters
    except ImportError:
        import pytest
        pytest.skip("MCP optional dependency is not installed")

    import stage3.mcp_cli as mcp_cli
    import stage3.mcp_interview_cli as interview_cli

    assert isinstance(
        StdioServerParameters(command="python", args=["-m", "stage3.mcp_servers.integration_mcp"]),
        StdioServerParameters,
    )
    assert hasattr(mcp_cli, "StdioServerParameters")
    assert hasattr(interview_cli, "StdioServerParameters")


def test_interview_mcp_cli_excludes_eval_only_tool():
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "mcp_interview_cli.py").read_text(encoding="utf-8")
    assert 'ground_truth_search' not in src
    assert 'evaluation_harness' not in src
    assert 'ground_truth_search' not in src


def test_runtime_timeout_budgets_are_tool_specific():
    from stage3.agent_runtime.permissions import TOOL_RUNTIME_CONFIG
    assert TOOL_RUNTIME_CONFIG["local_rag"]["timeout_sec"] == 15.0
    assert TOOL_RUNTIME_CONFIG["nowcoder_search"]["timeout_sec"] == 10.0
    assert TOOL_RUNTIME_CONFIG["memory_search"]["timeout_sec"] == 5.0
    assert TOOL_RUNTIME_CONFIG["ground_truth_search"]["timeout_sec"] == 5.0


def test_mcp_runtime_uses_central_timeout_budget(monkeypatch):
    import sys, types
    from stage3.agent_runtime.mcp_runtime import MCPToolSession

    class FakeTool:
        name = "local_rag"
        description = "rag"
        inputs = {"query": {"type": "string"}}
        output_schema = {"type": "object", "properties": {"items": {"type": "array"}}, "required": ["items"]}
        def __call__(self, **kwargs): return {"items": []}

    class Collection:
        tools = [FakeTool()]
        def __enter__(self): return self
        def __exit__(self, *args): return False

    class ToolCollection:
        @staticmethod
        def from_mcp(config, **kwargs): return Collection()

    monkeypatch.setitem(sys.modules, "smolagents", types.SimpleNamespace(ToolCollection=ToolCollection))
    with MCPToolSession({"command": "python"}, allowed_tools={"local_rag"}) as registry:
        assert registry.get("local_rag").timeout_sec == 15.0
        assert registry.get("local_rag").retries == 0





def test_interview_mcp_cli_has_profile_flag():
    from pathlib import Path
    cli_text = (Path(__file__).parents[1] / "mcp_interview_cli.py").read_text(encoding="utf-8")
    assert '--profile' in cli_text


def test_legacy_worker_module_exists():
    from pathlib import Path
    worker = Path(__file__).parents[1] / "agent_runtime" / "legacy_tool_worker.py"
    assert worker.exists()
    assert 'redirect_stdout' in worker.read_text(encoding="utf-8")


def test_mcp_raw_profile_cli_module_exists():
    from pathlib import Path
    assert Path("stage3/mcp_raw_profile_cli.py").exists()


def test_legacy_worker_env_forces_utf8(monkeypatch):
    from stage3.mcp_servers import interview_mcp

    seen = {}
    class DummyProc:
        def __init__(self, *args, **kwargs):
            seen.update(kwargs)
        def communicate(self, *args, **kwargs):
            return ('{"ok": true, "result": [], "profile": {}}', '')
        def kill(self):
            pass
        returncode = 0

    monkeypatch.setattr(interview_mcp.subprocess, 'Popen', DummyProc)
    interview_mcp._run_legacy_worker('local_rag', {'query': 'x', 'category': '', 'limit': 1}, 1.0)
    assert seen['env']['PYTHONUTF8'] == '1'
    assert seen['env']['PYTHONIOENCODING'] == 'utf-8'
    assert seen['errors'] == 'strict'
    assert seen['encoding'] == 'utf-8'
