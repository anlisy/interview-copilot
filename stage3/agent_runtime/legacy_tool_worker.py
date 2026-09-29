"""Isolated worker for legacy Interview Copilot tools.

The MCP stdio server must reserve stdout for JSON-RPC. Legacy business functions may
still print progress to stdout, so they are executed in a child process and their
stdout is captured there. Only one JSON result is emitted by this worker.
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import os
import time
from contextlib import redirect_stdout
from typing import Any


def _configure_utf8_stdio() -> None:
    """Force UTF-8 on the worker pipes; MCP parent decodes worker stdout as UTF-8."""
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="strict")


def _now_ms() -> int:
    return int(time.perf_counter() * 1000)


def _call(tool: str, args: dict[str, Any]) -> tuple[Any, dict[str, int]]:
    timings: dict[str, int] = {}
    if tool == "local_rag":
        t0 = _now_ms()
        from tools.knowledge_tools import search_knowledge
        timings["import_ms"] = _now_ms() - t0
        t1 = _now_ms()
        result = search_knowledge(
            args.get("query", ""),
            category=args.get("category") or None,
            top_k=int(args.get("limit", 5)),
        )
        timings["call_ms"] = _now_ms() - t1
        return result, timings
    if tool == "memory_search":
        t0 = _now_ms()
        from stage4.memory import MemoryStore
        timings["import_ms"] = _now_ms() - t0
        root = os.getenv("AGENT_MEMORY_ROOT", ".agent_memory").strip() or ".agent_memory"
        session_id = str(args.get("session_id", "")).strip() or None
        t1 = _now_ms()
        result = MemoryStore(root=root).recall(
            args.get("query", ""),
            limit=int(args.get("limit", 5)),
            session_id=session_id,
        )
        timings["call_ms"] = _now_ms() - t1
        return result, timings
    raise ValueError(f"unsupported legacy tool: {tool}")


def main() -> int:
    _configure_utf8_stdio()
    parser = argparse.ArgumentParser()
    parser.add_argument("--tool", required=True, choices=["local_rag", "memory_search"])
    args = parser.parse_args()
    raw = sys.stdin.read()
    request = json.loads(raw or "{}")

    started = _now_ms()
    print(f"[legacy-worker] start tool={args.tool}", file=sys.stderr, flush=True)
    captured = io.StringIO()
    try:
        parse_done = _now_ms()
        with redirect_stdout(captured):
            result, timings = _call(args.tool, request)
        elapsed = _now_ms() - started
        captured_text = captured.getvalue()
        print(
            f"[legacy-worker] done tool={args.tool} elapsed_ms={elapsed} captured_stdout_chars={len(captured_text)}",
            file=sys.stderr,
            flush=True,
        )
        profile = {
            "worker_total_ms": elapsed,
            "request_parse_ms": parse_done - started,
            **timings,
            "captured_stdout_chars": len(captured_text),
        }
        sys.stdout.write(json.dumps({"ok": True, "result": result, "profile": profile}, ensure_ascii=False))
        sys.stdout.flush()
        return 0
    except Exception as exc:  # noqa: BLE001
        elapsed = _now_ms() - started
        print(
            f"[legacy-worker] error tool={args.tool} elapsed_ms={elapsed} type={type(exc).__name__}: {exc}",
            file=sys.stderr,
            flush=True,
        )
        sys.stdout.write(json.dumps({"ok": False, "error": str(exc), "type": type(exc).__name__}, ensure_ascii=False))
        sys.stdout.flush()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
