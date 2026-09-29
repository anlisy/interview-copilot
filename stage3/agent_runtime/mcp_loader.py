from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator


class MCPToolLoadError(RuntimeError):
    pass


@contextmanager
def mcp_tool_collection(server_config: dict[str, Any], *, trust_remote_code: bool = False) -> Iterator[list[Any]]:
    """保持 MCP ToolCollection 生命周期，退出 context 时释放连接。"""
    try:
        from smolagents import ToolCollection
        with ToolCollection.from_mcp(
            server_config,
            trust_remote_code=trust_remote_code,
            structured_output=True,
        ) as collection:
            yield list(collection.tools)
    except Exception as exc:  # noqa: BLE001
        raise MCPToolLoadError(f"MCP Tool 加载失败: {exc}") from exc


def load_mcp_tools(server_config: dict[str, Any], *, trust_remote_code: bool = False):
    """兼容旧调用：返回 context manager，而不是让底层 MCP 连接提前关闭。"""
    return mcp_tool_collection(server_config, trust_remote_code=trust_remote_code)
