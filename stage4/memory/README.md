# Stage4 Memory

核心入口：`MemoryStore`

- `capture_turn()`：原始轨迹
- `capture_fact()`：长期记忆候选
- `consolidate()`：按 session 做阶段归纳落盘
- `recall()`：BM25 + Vector + RRF

`RedisSessionStore` 只负责热状态，不参与长期记忆检索。
