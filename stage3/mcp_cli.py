from __future__ import annotations

import argparse
import json
import sys

from mcp import StdioServerParameters
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT.parent) not in sys.path:
    sys.path.insert(0, str(ROOT.parent))

from stage3.agent_runtime.mcp_runtime import MCPRuntimeError, MCPToolSession
from stage3.agent_runtime.tool_executor import ToolExecutor
from stage3.agent_runtime.tool_models import ToolCallContext
from stage3.agent_runtime.tool_policy import ToolPolicy


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage 3 real MCP integration smoke test")
    parser.add_argument("--text", default="mcp-runtime-ok")
    args = parser.parse_args()

    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "stage3.mcp_servers.integration_mcp"],
    )
    print("🧰 Stage 3 MCP Integration")
    print(f"Server: stage3.mcp_servers.integration_mcp (stdio)")
    try:
        with MCPToolSession(
            params,
            allowed_tools={"mcp_echo"},
            agent_acl={"mcp_echo": frozenset({"interviewer"})},
            strict_allowlist=True,
            trust_remote_code=True,
        ) as registry:
            print(f"Discovered: {', '.join(registry.names())}")
            result = ToolExecutor(registry, ToolPolicy()).call(
                "mcp_echo",
                {"text": args.text},
                ToolCallContext(agent="interviewer"),
            )
            print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))
            return 0 if result.ok and result.output == {"echo": args.text, "length": len(args.text)} else 1
    except MCPRuntimeError as exc:
        print(f"❌ MCP runtime: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
