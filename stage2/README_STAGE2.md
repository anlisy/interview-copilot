# Stage 2 README

Stage 2 将 Interview Copilot 的面试领域经验封装为可发现、可选择、可激活的 Skill，并把 Skill 选择接入 Stage 1 Orchestrator 前置链路。

## 核心链路

```text
Task
  ↓
Skill Registry（只读 metadata）
  ↓
Skill Resolver（候选召回）
  ↓
Rule / JEV Selector（当前规则基线）
  ↓
Skill Activation（加载完整 SKILL.md）
  ↓
Stage 1 Orchestrator
  ↓
Stage 1 Harness
  ↓
Agent / Tool

说明：Skill 只在当前 Workflow 阶段存在其负责的 action 时激活。
INIT 等前置阶段的 diagnose 等动作仍由 Orchestrator/Harness 独立管理，不会被 Skill contract 误拦截。
```

Skill 只提供“怎么做”的领域方法、检查项和输出标准；它不能越过 Stage 1 Harness 执行 Agent 或 Tool。

### 选择边界
- 明确信号/意图命中时可以激活 Skill。
- 低于默认 `min_score=0.15` 但存在明确 Skill signal/intent 的任务仍可激活，避免中文短任务被过严过滤。
- 既没有明确 signal/intent、得分又不足的任务不强行选择 Skill，回退到基础 Orchestrator，并在 Trace 中记录 `skill_not_matched`。
- `question-design` 等 Skill 的 `metadata.allowed_actions` 必须与运行时 binding 一致，否则注册校验直接失败。

## 测试

```bat
python -m pytest stage2\tests -q

# 当前基线：30 passed
```

## Managed Runtime 冒烟

需要项目已存在 `stage1/` 且智谱 API Key 有效：

```bat
python -m stage2.cli_managed --task "根据简历设计项目深挖面试题，避免重复"

# 默认从 DIAGNOSIS 阶段进入 Skill-owned action；如需验证前置阶段：
python -m stage2.cli_managed --start-stage INIT --task "根据简历设计项目深挖面试题，避免重复"
```

当前不训练 JEV。后续 JEV 只替换最终 Selector。
