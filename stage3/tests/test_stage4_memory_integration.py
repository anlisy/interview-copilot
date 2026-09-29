from __future__ import annotations

from stage3.agent_runtime.legacy_tool_worker import _call
from stage4.memory import MemoryStore


def test_stage3_memory_search_reads_stage4_store(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_MEMORY_ROOT", str(tmp_path / ".agent_memory"))
    store = MemoryStore(root=tmp_path / ".agent_memory")
    store.capture_fact(
        "session-a",
        "候选人的 Redis 项目使用互斥锁处理缓存击穿，后续可以追问热点 Key 治理。",
        stage="FOLLOWUP",
        confidence=0.95,
    )

    items, timings = _call(
        "memory_search",
        {"query": "Redis 缓存击穿 热点 Key", "limit": 3, "session_id": "session-a"},
    )

    assert items
    assert items[0]["session_id"] == "session-a"
    assert "互斥锁" in items[0]["content"]
    assert timings["call_ms"] >= 0


def test_stage3_memory_search_respects_stage4_session_filter(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_MEMORY_ROOT", str(tmp_path / ".agent_memory"))
    store = MemoryStore(root=tmp_path / ".agent_memory")
    store.capture_fact("session-a", "A 会话的 Redis 缓存击穿经验。")
    store.capture_fact("session-b", "B 会话的 Redis 缓存击穿经验。")

    items, _ = _call(
        "memory_search",
        {"query": "Redis 缓存击穿 经验", "limit": 5, "session_id": "session-a"},
    )

    assert items
    assert {item["session_id"] for item in items} == {"session-a"}
