"""Deterministic MCP server used for local protocol integration tests."""
from __future__ import annotations

try:
    from pydantic import BaseModel
    from mcp.server.fastmcp import FastMCP
except ImportError:  # pragma: no cover
    BaseModel = None
    FastMCP = None


if FastMCP is not None and BaseModel is not None:
    mcp = FastMCP("interview-copilot-integration")

    class EchoResult(BaseModel):
        echo: str
        length: int

    @mcp.tool(name="mcp_echo", description="回显输入，用于验证 MCP discovery/call/structured output 生命周期")
    def mcp_echo(text: str) -> EchoResult:
        return EchoResult(echo=text, length=len(text))
else:
    mcp = None


if __name__ == "__main__":
    if mcp is None:
        raise SystemExit('未安装 MCP 依赖，请执行: pip install "smolagents[mcp]==1.26.0"')
    mcp.run(transport="stdio")
