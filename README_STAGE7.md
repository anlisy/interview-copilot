# Stage7-A：Memory Consolidation

Stage7 不替代 Stage4，而是在 Stage4 的 Raw Trajectory / Durable Memory 之上增加“跨 Session 沉淀”。

## 架构

```text
Session finished
      |
      v
Lifecycle Hook
      |
      v
Raw Trajectory
      |
      v
Memory Extractor
  |            |
 Rule         GLM
      \        /
       Candidate Memory
              |
        Dedup / Conflict
              |
      +-------+-------+
      |       |       |
     new   duplicate conflict
      |       |       |
      v       x     review
 Durable Memory
      ^
      |
 Checkpoint / Resume
```

## Hook 是否需要

需要，但使用“Session 生命周期 Hook”，而不是每个 token 或每个模型 step 都直接写长期 Memory。Hook 的职责是发现 `session_finished` 并触发一次 consolidation。当前 Stage4 已经记录 Raw Trajectory，因此 Stage7-A 不需要为了沉淀再增加 smolagents `step_callbacks`；只有未来某些 Agent 路径绕过 Stage4 `record_turn` 时，才考虑用 smolagents 的 step callback 做轨迹补采集。

## Checkpoint 是否需要

需要。Consolidation 至少包含 extract、resolve、commit 三个阶段，中间任何一步失败都可能留下半成品。Checkpoint 保存 source fingerprint、candidate、resolution 和 committed ids，job id 由 policy + session + trajectory fingerprint 计算，保证同一批输入重复触发时可以恢复或直接幂等返回。

## 运行

规则模式：

```cmd
python -m stage7.cli --session-id <SESSION_ID> --mode rule
```

智谱模式：

```cmd
set ZHIPU_API_KEY=...
set ZHIPU_MODEL=glm-4-flash
set ZHIPU_BASE_URL=https://open.bigmodel.cn/api/paas/v4
python -m stage7.cli --session-id <SESSION_ID> --mode glm
```

## 设计边界

Stage7-A 不自动把“相似但相反”的新记忆覆盖旧记忆，只产生 conflict。后续 Stage7-B 再加入跨 Session evidence aggregation、版本化、stale/superseded 和更强的语义冲突判定。
