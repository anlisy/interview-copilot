from __future__ import annotations

import asyncio
import json
import sys
import time
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main_async() -> int:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "stage3.mcp_servers.interview_mcp_stdio"],
    )
    started = time.perf_counter()
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init_t = time.perf_counter()
            await session.initialize()
            init_ms = (time.perf_counter() - init_t) * 1000

            list_t = time.perf_counter()
            tools = await session.list_tools()
            list_ms = (time.perf_counter() - list_t) * 1000

            args = {"query": "Redis 缓存击穿", "category": "", "limit": 3}
            call1_t = time.perf_counter()
            result1 = await session.call_tool("local_rag", args)
            call1_ms = (time.perf_counter() - call1_t) * 1000

            call2_t = time.perf_counter()
            result2 = await session.call_tool("local_rag", args)
            call2_ms = (time.perf_counter() - call2_t) * 1000

            payload = {
                "transport": "stdio",
                "initialize_ms": round(init_ms, 2),
                "list_tools_ms": round(list_ms, 2),
                "tool_names": [getattr(t, "name", "") for t in tools.tools],
                "raw_call1_ms": round(call1_ms, 2),
                "raw_call2_ms": round(call2_ms, 2),
                "result1_structured": getattr(result1, "structuredContent", None),
                "result2_structured": getattr(result2, "structuredContent", None),
                "total_session_ms": round((time.perf_counter() - started) * 1000, 2),
            }
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0


def main() -> int:
    return asyncio.run(main_async())


if __name__ == "__main__":
    raise SystemExit(main())
