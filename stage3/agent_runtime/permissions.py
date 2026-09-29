from __future__ import annotations

# Single source of truth for the Interview Copilot Tool permission model.
AGENT_TOOL_MATRIX = {
    "interviewer": frozenset({"local_rag", "nowcoder_search", "memory_search"}),
    "scorer": frozenset(),
    "reviewer": frozenset({"memory_search"}),
    "evaluation_harness": frozenset({"ground_truth_search"}),
}

TOOL_AGENT_MATRIX = {
    "local_rag": frozenset({"interviewer"}),
    "nowcoder_search": frozenset({"interviewer"}),
    "memory_search": frozenset({"interviewer", "reviewer"}),
    "ground_truth_search": frozenset({"evaluation_harness"}),
}

TOOL_ACTION_MATRIX = {
    "local_rag": {
        "interviewer": frozenset({"diagnose", "generate", "followup"}),
    },
    "nowcoder_search": {
        "interviewer": frozenset({"generate"}),
    },
    "memory_search": {
        "interviewer": frozenset({"diagnose", "generate", "followup"}),
        "reviewer": frozenset({"review"}),
    },
    "ground_truth_search": {
        "evaluation_harness": frozenset({"retrieve_ground_truth"}),
    },
}

# These are monotonic safety rules: an MCP adapter may narrow permissions, but
# it must never widen these centrally-defined restrictions for known tools.
TOOL_EVAL_DENY = frozenset({"nowcoder_search"})
TOOL_EVAL_ONLY = frozenset({"ground_truth_search"})


# Per-tool runtime budgets. These are operational limits, not permission grants.
# local_rag can incur first-call Chroma/embedding cold-start latency, so it gets a
# larger budget; network-backed search has its own bounded budget.
TOOL_RUNTIME_CONFIG = {
    "local_rag": {"timeout_sec": 15.0, "retries": 0, "idempotent": True},
    "nowcoder_search": {"timeout_sec": 10.0, "retries": 0, "idempotent": True},
    "memory_search": {"timeout_sec": 5.0, "retries": 0, "idempotent": True},
    "ground_truth_search": {"timeout_sec": 5.0, "retries": 0, "idempotent": True},
}


def validate_permission_matrices() -> None:
    """Fail fast if the central permission tables contradict each other."""
    for agent, tools in AGENT_TOOL_MATRIX.items():
        for tool in tools:
            if agent not in TOOL_AGENT_MATRIX.get(tool, frozenset()):
                raise ValueError(f"Agent/Tool 映射不一致: {agent} -> {tool}")
    for tool, agents in TOOL_AGENT_MATRIX.items():
        for agent in agents:
            if tool not in AGENT_TOOL_MATRIX.get(agent, frozenset()):
                raise ValueError(f"Tool/Agent 映射不一致: {tool} -> {agent}")
    for tool, action_map in TOOL_ACTION_MATRIX.items():
        known_agents = TOOL_AGENT_MATRIX.get(tool, frozenset())
        for agent, actions in action_map.items():
            if agent not in known_agents:
                raise ValueError(f"Action ACL 扩大了 Agent ACL: {tool} -> {agent}")
            if not actions:
                raise ValueError(f"Action ACL 不能为空: {tool} -> {agent}")


validate_permission_matrices()
