# Stage8：Online Decision-Memory-Agent Runtime

Stage8 将 Stage6 Decision、Stage4 Context/Memory、Stage3 ToolPolicy、Stage7 Memory Consolidation 和现有 Stage1 Agent 接成在线闭环。

## Stage8-C：真实 Agent Runtime + State Bridge + Online Memory Capture

核心链路：

```text
Session State
   ↓
Stage6 Skill / Tool / Intent
   ↓
Stage4 Context Manager
   ↓
Stage1 Interviewer / Scorer / Reviewer
   ↓
Raw Trajectory
   ↓
Online Memory Candidate
   ↓
Stage7-A/B Consolidation
   ↓
Stable Claim / Version
```

### 1. Real Agent Runtime

`Stage1AgentRunner` 复用现有 Stage1 的 `InterviewerAgent / ScorerAgent / ReviewerAgent`，不复制一套新的 Agent 逻辑。Agent 实例只在当前进程内缓存，不进入 Session 持久化。

旧 Stage1 Agent 没有 `context` 参数时，`Stage1ContextInjector` 在调用期间临时包装对应 `tools/*_tools.py` 的 `_load_prompt`，把 Stage8 受控 Context 注入原有 Prompt，再恢复原函数；使用锁避免并发请求互相污染。

### 2. State Bridge

`StateBridge` 只同步可序列化状态，不持久化 Supervisor/LLM client：

```text
INIT → GENERATING → ASKING
ASKING → SCORING → ASKING
ASKING → SCORING → REVIEWING → FINISHED
```

Session 文件/Redis 仍只保存 `SessionState`。

### 3. Online Memory Capture

只有用户回答或显式 `--memory-candidate` 才能进入长期记忆候选；模型生成的 assistant 文本不会被当作用户事实。

默认自动规则需要明显的第一人称经验表达，如“我负责/我做过/我解决过”等，并要求最小文本长度；显式标记可以覆盖规则筛选。

长期记忆仍必须经过 Stage7 Consolidation 才进入 Durable Memory / Stable Claim。

## CLI

Stage8 smoke：

```cmd
python -m stage8.cli --session-id demo --task "根据 Redis 项目设计项目深挖面试题" --engine rule --text-mode echo
```

JEV + GLM：

```cmd
set ZHIPU_API_KEY=你的key
set ZHIPU_MODEL=glm-4-flash
set ZHIPU_BASE_URL=https://open.bigmodel.cn/api/paas/v4
python -m stage8.cli --session-id demo --task "根据 Redis 项目设计项目深挖面试题" --engine jev --text-mode zhipu
```

真实 Stage1 Interviewer：

```cmd
python -m stage8.cli --session-id demo --task "生成面试题" --agent interviewer --action generate --agent-mode stage1 --engine rule --resume "候选人简历" --jd "Java后端岗位JD" --total 5
```

在线采集回答为长期记忆候选：

```cmd
python -m stage8.cli --session-id demo-answer --task "请介绍一个你做过的缓存治理项目" --engine rule --text-mode echo --answer "我负责过 Redis 缓存治理，解决过缓存击穿。" --memory-candidate --finish
```

## Stage8-C 最终收口

### 4. 终态幂等与执行合同

- `FINISHED` 是终态：重复 `finish` 直接返回上一次结果，不重新执行 Decision、Agent、Raw Trajectory 或 Stage7。
- `FINISHED` 状态下的普通新请求直接拒绝，防止绕过状态机继续执行。
- 当 CLI 显式指定 `agent/action` 时，`agent/action` 是执行硬约束；若 Decision Layer 选出的 Skill 与执行合同不一致，保留原始 Decision，同时由显式 Agent/Action 决定实际 Skill，并记录 `decision_action_mismatch`。
- `RouteResult` 同时保留兼容字段 `route/fallback` 与推荐字段 `decision_route/fallback_applied`：前者兼容旧调用，后者分别表示“决策策略路径”和“是否真的发生 fallback engine 执行”。
- `last_memory_capture`、`last_consolidation`、`last_turn_id` 随 SessionState 持久化，便于跨请求恢复与调试。

### 5. 测试命令

当前 Stage8-C 独立测试共 18 个：

```cmd
python -m pytest -q stage8\tests
```

完整项目回归：

```cmd
python -m pytest -q
```

## 设计边界

- Stage6 Decision 负责有限集合选择，不负责长文本生成。
- Stage3 ToolPolicy/ACL/Executor 是工具执行的最终约束。
- Stage4 Memory 负责 Recall 与 Context 工作集。
- Stage7 负责从 Raw Trajectory 中提炼、聚合、版本化长期事实。
- Stage8 负责把上述能力编排成在线请求生命周期。
