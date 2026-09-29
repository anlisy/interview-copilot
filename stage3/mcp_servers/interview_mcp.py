"""Interview Copilot MCP Server.

Only explicitly registered interview tools are exposed. Ground-truth retrieval is
kept outside the normal interview MCP server.

Important stdio rule: stdout belongs to MCP JSON-RPC. Legacy application tools are
therefore isolated in a child process so their historical progress prints can never
pollute the MCP protocol stream.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from typing import Any

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:  # pragma: no cover
    FastMCP = None

mcp = FastMCP("interview-copilot-tools") if FastMCP else None


def _ms() -> int:
    return int(time.perf_counter() * 1000)


def _profile_enabled() -> bool:
    return os.getenv("INTERVIEW_MCP_PROFILE", "0") == "1"


def _profile(message: str) -> None:
    if _profile_enabled():
        print(f"[MCP {time.strftime('%H:%M:%S')}.{int(time.time()*1000)%1000:03d}] {message}", file=sys.stderr, flush=True)


def _run_legacy_worker(tool: str, payload: dict[str, Any], timeout_sec: float) -> tuple[Any, dict[str, Any]]:
    started = _ms()
    _profile(f"legacy_worker_start tool={tool} timeout_sec={timeout_sec}")
    child_env = os.environ.copy()
    # Windows pipes inherit the system code page unless UTF-8 mode is forced.
    # The worker protocol is JSON over UTF-8, so pin the child stdio encoding.
    child_env["PYTHONUTF8"] = "1"
    child_env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.Popen(
        [sys.executable, "-m", "stage3.agent_runtime.legacy_tool_worker", "--tool", tool],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="strict",
        env=child_env,
    )
    communicate_started = _ms()
    try:
        stdout, stderr = proc.communicate(json.dumps(payload, ensure_ascii=False), timeout=timeout_sec)
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, stderr = proc.communicate()
        _profile(f"legacy_worker_timeout tool={tool} elapsed_ms={_ms()-started} stderr={stderr[-1000:]!r}")
        raise TimeoutError(f"legacy tool {tool} timeout after {timeout_sec:.3f}s")

    if stderr:
        for line in stderr.rstrip().splitlines():
            _profile(f"legacy_worker_stderr {line}")
    _profile(f"legacy_worker_done tool={tool} elapsed_ms={_ms()-started} returncode={proc.returncode}")
    if not stdout.strip():
        raise RuntimeError(f"legacy tool {tool} returned empty stdout")
    response = json.loads(stdout)
    if not response.get("ok"):
        raise RuntimeError(f"legacy tool {tool} failed: {response.get('type')}: {response.get('error')}")
    profile = dict(response.get("profile") or {})
    profile["server_communicate_ms"] = _ms() - communicate_started
    profile["server_total_ms"] = _ms() - started
    return response.get("result"), profile


def _authorized_nowcoder_search(query: str, company: str, role: str, limit: int) -> list[dict[str, Any]]:
    base = os.getenv("NOWCODER_SEARCH_URL", "").strip()
    if not base:
        raise RuntimeError("未配置 NOWCODER_SEARCH_URL；请接入用户拥有/获授权的搜索服务")
    payload = json.dumps({"query": query, "company": company, "role": role, "limit": limit}).encode("utf-8")
    req = urllib.request.Request(base, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data.get("items", [])

if mcp is not None:
    @mcp.tool(name="nowcoder_search")
    def nowcoder_search(query: str, company: str = "", role: str = "", limit: int = 5) -> dict[str, Any]:
        started = _ms(); _profile(f"tool_start name=nowcoder_search query_len={len(query)}")
        limit = max(1, min(int(limit), 10))
        result = {"items": _authorized_nowcoder_search(query, company, role, limit)}
        _profile(f"tool_done name=nowcoder_search elapsed_ms={_ms()-started}")
        return result

    @mcp.tool(name="local_rag")
    def local_rag(query: str, category: str = "", limit: int = 5) -> dict[str, Any]:
        started = _ms(); _profile(f"tool_start name=local_rag query_len={len(query)} category={category!r} limit={limit}")
        limit = max(1, min(int(limit), 10))
        items, profile = _run_legacy_worker("local_rag", {"query": query, "category": category, "limit": limit}, timeout_sec=20.0)
        tool_elapsed = _ms() - started
        _profile(f"tool_done name=local_rag elapsed_ms={tool_elapsed} result_count={len(items) if hasattr(items,'__len__') else 'NA'} profile={profile}")
        output = {"items": items}
        if _profile_enabled():
            output["_profile"] = {"mcp_handler_ms": tool_elapsed, **profile}
        return output

    @mcp.tool(name="memory_search")
    def memory_search(query: str, limit: int = 5) -> dict[str, Any]:
        started = _ms(); _profile(f"tool_start name=memory_search query_len={len(query)} limit={limit}")
        limit = max(1, min(int(limit), 10))
        items, profile = _run_legacy_worker("memory_search", {"query": query, "limit": limit}, timeout_sec=8.0)
        tool_elapsed = _ms() - started
        _profile(f"tool_done name=memory_search elapsed_ms={tool_elapsed} result_count={len(items) if hasattr(items,'__len__') else 'NA'} profile={profile}")
        output = {"items": items}
        if _profile_enabled():
            output["_profile"] = {"mcp_handler_ms": tool_elapsed, **profile}
        return output

if __name__ == "__main__":
    if mcp is None:
        raise SystemExit('未安装 MCP 依赖，请执行: pip install "smolagents[mcp]==1.26.0"')
    mcp.run(transport="stdio")
