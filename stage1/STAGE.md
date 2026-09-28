# 阶段 1：中心编排 + Harness

## 本阶段目标
在不重写现有 Interviewer / Scorer / Reviewer 的前提下，引入中心 Orchestrator，并把真实执行纳入 Harness 控制边界。

## 运行模型

`Goal + State + Observations -> Orchestrator(智谱 API) -> Decision(JSON) -> Harness(强校验) -> Handler/旧 Agent -> Trace(JSONL)`

Orchestrator 只决定 `agent/action`；Harness 决定“能不能执行”。

## Harness 校验

- Agent 白名单
- Action 白名单
- Tool 白名单
- Eval 禁用工具
- session_version 乐观并发控制
- max_steps
- max_followup（每个主问题重新计数）
- token budget / cost budget
- action timeout 检测
- action result schema
- workflow state transition
- dataclass / Pydantic / mapping 结果适配

## 这版额外修复

- 修复 `python -m stage1.cli` 与 `python stage1\cli.py` 两种启动方式的模块路径。
- 修复 `workflow.yaml` 路径解析。
- 修复 Supervisor 评分 dataclass 与 Harness object schema 的兼容。
- 修复 reviewer 返回 Markdown 字符串与 schema 不匹配。
- review 真实执行也经过 Orchestrator + Harness，并最终迁移到 `FINISHED`。
- 非法 `next_stage` 在 handler 执行前拒绝，避免先产生副作用。
- 追问次数在进入下一道主问题时重置。
- Trace 中对 resume/JD/answer/content 等敏感字段做哈希摘要，并清理 session id 文件名。
- Orchestrator 决策强制校验四个字段：`agent/action/session_version/reason_code`。
- Eval 模式、Tool ACL 与 decision tool 字段同时校验。
- Workflow 加载时验证 action/tool/stage 引用关系。

## 智谱 API

默认使用 OpenAI-compatible Chat Completions 风格的智谱 API：
`https://open.bigmodel.cn/api/paas/v4`

模型通过 `ZHIPU_MODEL` 配置；不要把 API Key 写进代码或提交到 Git。

## 验收命令

```bat
python -m pytest stage1\tests -q
python -m py_compile stage1\agent_runtime\workflow.py stage1\agent_runtime\trace.py stage1\agent_runtime\harness.py stage1\agent_runtime\zhipu_client.py stage1\agent_runtime\orchestrator.py stage1\cli.py
```

真实智谱测试前：

```bat
set ZHIPU_API_KEY=你的Key
set ZHIPU_MODEL=你的模型名
set ZHIPU_BASE_URL=https://open.bigmodel.cn/api/paas/v4
set AGENT_ORCHESTRATOR=1
python -m stage1.cli
```

也支持：

```bat
python stage1\cli.py
```

## 当前边界

Stage 1 的 token/cost 预算目前直接统计 Orchestrator 的智谱调用；现有 Supervisor 内部模型调用尚未统一纳入同一个 usage collector，后续需要在模型层统一接入。

action timeout 目前保证 Harness 能及时判定并返回超时错误，但 Python 线程本身无法被安全强制终止，因此有副作用的长任务后续应迁移到可终止的 worker/process 边界。

本阶段不实现 Skill、MCP Tool 和 Memory；这些分别在后续阶段实现。
