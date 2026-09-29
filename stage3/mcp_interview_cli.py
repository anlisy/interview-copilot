from __future__ import annotations

import argparse
import json
import sys

from mcp import StdioServerParameters

from stage3.agent_runtime.mcp_runtime import MCPRuntimeError, MCPToolSession
from stage3.agent_runtime.permissions import AGENT_TOOL_MATRIX, TOOL_EVAL_DENY
from stage3.agent_runtime.tool_executor import ToolExecutor
from stage3.agent_runtime.tool_models import ToolCallContext
from stage3.agent_runtime.tool_policy import ToolPolicy


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage 3 real Interview Copilot MCP tool call")
    parser.add_argument("--agent", default="interviewer", choices=["interviewer", "scorer", "reviewer"])
    parser.add_argument("--tool", required=True, choices=["local_rag", "nowcoder_search", "memory_search"])
    parser.add_argument("--action", required=True)
    parser.add_argument("--eval", action="store_true")
    parser.add_argument("--query", default="Redis 缓存击穿")
    parser.add_argument("--category", default="", help="local_rag 分类；留空表示不限定分类")
    parser.add_argument("--company", default="", help="nowcoder_search 公司过滤条件")
    parser.add_argument("--role", default="", help="nowcoder_search 岗位过滤条件")
    parser.add_argument("--profile", action="store_true", help="打印 Host/MCP 分段耗时")
    args = parser.parse_args()
    if args.profile:
        import os
        os.environ["INTERVIEW_MCP_PROFILE"] = "1"

    allowed = set(AGENT_TOOL_MATRIX.get(args.agent, frozenset()))
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "stage3.mcp_servers.interview_mcp_stdio"],
    )
    print("🧰 Stage 3 Interview MCP")
    print(f"Agent: {args.agent}, action: {args.action}, eval: {args.eval}")
    try:
        with MCPToolSession(
            params,
            allowed_tools=allowed,
            strict_allowlist=True,
            trust_remote_code=True,
            eval_denied=TOOL_EVAL_DENY,
            eval_only=frozenset(),
        ) as registry:
            policy = ToolPolicy()
            ctx = ToolCallContext(
                agent=args.agent,
                eval_mode=args.eval,
                action=args.action,
                principal_type="agent",
            )
            print(f"Visible tools: {', '.join(policy.visible_tools(registry, ctx)) or '<none>'}")
            if args.tool == "nowcoder_search":
                arguments = {"query": args.query, "company": args.company, "role": args.role, "limit": 3}
            elif args.tool == "local_rag":
                arguments = {"query": args.query, "category": args.category, "limit": 3}
            elif args.tool == "memory_search":
                arguments = {"query": args.query, "limit": 3}
            else:
                arguments = {"query": args.query, "limit": 3}
            import time
            call_started = time.perf_counter()
            if args.profile:
                print(f"[HOST] tool_call_start t={time.strftime('%H:%M:%S')}.{int(time.time()*1000)%1000:03d} tool={args.tool}", file=sys.stderr, flush=True)
            result = ToolExecutor(registry, policy).call(args.tool, arguments, ctx)
            host_ms = int((time.perf_counter() - call_started) * 1000)
            if args.profile:
                print(f"[HOST] tool_call_done elapsed_ms={host_ms} ok={result.ok} code={result.error_code}", file=sys.stderr, flush=True)
            print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))
            return 0 if result.ok else 2
    except MCPRuntimeError as exc:
        print(f"❌ MCP runtime: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
