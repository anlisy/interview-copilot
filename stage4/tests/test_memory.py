from stage4.memory.memory_store import MemoryStore
from stage4.memory.models import MemoryRecord
from stage4.memory.rrf import reciprocal_rank_fusion
from stage4.agent_runtime.context_manager import ContextBudget, ContextManager, ContextSection
from stage4.agent_runtime.token_counter import ConservativeCounter


def test_capture_raw_and_candidate(tmp_path):
    store = MemoryStore(tmp_path / "mem")
    store.capture_turn("s1", "user", "我负责 Redis 缓存击穿治理", stage="ANSWER")
    store.capture_fact("s1", "项目使用 Redis 互斥锁处理缓存击穿", stage="ANSWER", importance=0.8)
    rows = store.raw.read("s1")
    assert len(rows) == 1
    hits = store.recall("Redis 缓存击穿", limit=3)
    assert hits and "互斥锁" in hits[0]["content"]


def test_consolidate_writes_daily(tmp_path):
    store = MemoryStore(tmp_path / "mem")
    store.capture_turn("s1", "user", "一个普通回答")
    store.capture_turn("s1", "user", "一个重要项目事实", metadata={"importance": 0.9, "memory_candidate": True})
    path = store.consolidate("s1")
    assert path.exists()
    assert "项目事实" in path.read_text(encoding="utf-8")


def test_rrf_merges_rankings():
    merged = reciprocal_rank_fusion(
        [[("a", 1.0), ("b", 0.9)], [("b", 0.99), ("c", 0.8)]],
        k=10,
        limit=3,
    )
    assert merged[0][0] in {"a", "b"}
    assert {x[0] for x in merged} == {"a", "b", "c"}


def test_context_respects_token_budget():
    c = ContextManager(ContextBudget(total_tokens=80, output_reserve=20), ConservativeCounter())
    out = c.assemble([
        ContextSection("系统契约", "system " * 20, 100, 5),
        ContextSection("当前任务", "task", 100, 5),
        ContextSection("历史", "history " * 30, 10),
    ])
    assert "当前任务" in out
    assert c.counter.count(out) <= 60


def test_context_keeps_fixed_order_after_priority_packing():
    c = ContextManager(ContextBudget(total_tokens=300, output_reserve=50), ConservativeCounter())
    out = c.assemble([
        ContextSection("系统契约", "sys", 100),
        ContextSection("工作流", "flow", 90),
        ContextSection("当前任务", "task", 100),
    ])
    assert out.index("系统契约") < out.index("工作流") < out.index("当前任务")
