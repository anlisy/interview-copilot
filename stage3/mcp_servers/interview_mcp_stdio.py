"""stdio entrypoint for Interview Copilot MCP tools.

This module is intentionally thin so smolagents can spawn it as a child
process with StdioServerParameters.
"""
from __future__ import annotations

from .interview_mcp import mcp


if __name__ == "__main__":
    if mcp is None:
        raise SystemExit('未安装 MCP 依赖，请执行: pip install "smolagents[mcp]==1.26.0"')
    mcp.run(transport="stdio")
