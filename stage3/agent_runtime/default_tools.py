from __future__ import annotations

from .tool_models import ToolSpec
from .tool_registry import ToolRegistry

COMMON_OBJECT = {"type": "object", "additionalProperties": True}
ITEM_RESULT = {
    "type": "object",
    "properties": {"items": {"type": "array"}},
    "required": ["items"],
    "additionalProperties": True,
}

from .permissions import AGENT_TOOL_MATRIX, TOOL_AGENT_MATRIX, TOOL_ACTION_MATRIX, TOOL_RUNTIME_CONFIG

def build_default_registry() -> ToolRegistry:
    specs = [
        ToolSpec(
            name="local_rag",
            description="查询本地面试知识库",
            input_schema=COMMON_OBJECT,
            output_schema=ITEM_RESULT,
            allowed_agents=TOOL_AGENT_MATRIX["local_rag"],
            allowed_actions=TOOL_ACTION_MATRIX["local_rag"],
            timeout_sec=TOOL_RUNTIME_CONFIG["local_rag"]["timeout_sec"],
            retries=TOOL_RUNTIME_CONFIG["local_rag"]["retries"],
            idempotent=TOOL_RUNTIME_CONFIG["local_rag"]["idempotent"],
            source="mcp:interview",
        ),
        ToolSpec(
            name="nowcoder_search",
            description="查询用户自己提供/获授权的面经搜索服务",
            input_schema=COMMON_OBJECT,
            output_schema=ITEM_RESULT,
            allowed_agents=TOOL_AGENT_MATRIX["nowcoder_search"],
            eval_deny=True,
            allowed_actions=TOOL_ACTION_MATRIX["nowcoder_search"],
            timeout_sec=TOOL_RUNTIME_CONFIG["nowcoder_search"]["timeout_sec"],
            retries=TOOL_RUNTIME_CONFIG["nowcoder_search"]["retries"],
            idempotent=TOOL_RUNTIME_CONFIG["nowcoder_search"]["idempotent"],
            source="mcp:interview",
        ),
        ToolSpec(
            name="memory_search",
            description="查询长期面试记忆",
            input_schema=COMMON_OBJECT,
            output_schema=ITEM_RESULT,
            allowed_agents=TOOL_AGENT_MATRIX["memory_search"],
            allowed_actions=TOOL_ACTION_MATRIX["memory_search"],
            timeout_sec=TOOL_RUNTIME_CONFIG["memory_search"]["timeout_sec"],
            retries=TOOL_RUNTIME_CONFIG["memory_search"]["retries"],
            idempotent=TOOL_RUNTIME_CONFIG["memory_search"]["idempotent"],
            source="mcp:interview",
        ),
        ToolSpec(
            name="ground_truth_search",
            description="评测基准真值检索，仅允许受控 Eval 组件；普通 Agent 永远不能使用",
            input_schema=COMMON_OBJECT,
            output_schema=ITEM_RESULT,
            allowed_agents=TOOL_AGENT_MATRIX["ground_truth_search"],
            eval_only=True,
            allowed_actions=TOOL_ACTION_MATRIX["ground_truth_search"],
            timeout_sec=TOOL_RUNTIME_CONFIG["ground_truth_search"]["timeout_sec"],
            retries=TOOL_RUNTIME_CONFIG["ground_truth_search"]["retries"],
            idempotent=TOOL_RUNTIME_CONFIG["ground_truth_search"]["idempotent"],
            source="evaluation-only",
        ),
    ]
    return ToolRegistry(specs)
