from __future__ import annotations

import argparse
from pathlib import Path

from .agent_runtime.memory_runtime import MemoryAwareRuntime
from .memory.memory_store import MemoryStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage4 分层记忆 + Context Manager")
    parser.add_argument("--session", default="stage4-demo")
    parser.add_argument("--query", default="分析候选人的 Redis 缓存击穿项目")
    parser.add_argument("--root", default=".agent_memory")
    args = parser.parse_args()

    store = MemoryStore(Path(args.root))
    runtime = MemoryAwareRuntime(store)

    # 演示长期记忆候选写入；真实运行时由评分/复盘结果决定是否写入。
    if not store.recall("Redis 缓存击穿", limit=1):
        runtime.record_memory_candidate(
            args.session,
            "候选人的项目里使用 Redis + 互斥锁处理缓存击穿，但热点 Key 没有进一步治理。",
            stage="ANSWER_REVIEW",
            confidence=0.88,
            importance=0.82,
            memory_type="project_fact",
            metadata={"topic": "redis", "memory_candidate": True},
        )

    bundle = runtime.prepare_context(
        args.session,
        args.query,
        workflow="INTERVIEW -> QUESTION -> ANSWER -> SCORE -> REVIEW",
        skill="优先围绕项目事实深挖，避免重复已经确认的问题。",
        profile="Java 后端 / AI Agent 工程方向",
        recent_turns="当前还没有新的回答。",
    )
    print("memories:")
    for hit in bundle.memories:
        print(f"- {hit['memory_type']} | {hit['fused_score']} | {hit['content']}")
    print("\ncontext:")
    print(bundle.rendered)


if __name__ == "__main__":
    main()
