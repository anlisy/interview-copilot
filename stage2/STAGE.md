# Stage 2 — Interview Domain Skills

## 已实现
- 6 个面试领域 Skill
- SKILL.md frontmatter 校验
- metadata-only discovery
- Skill Resolver
- deterministic Rule Selector
- progressive disclosure activation
- Skill -> Action contract
- Stage 1 Orchestrator / Harness 集成
- Skill selection / rejection / no-match fallback Trace
- Skill binding 与 SKILL.md allowed_actions 一致性校验
- 无关任务不会被强制绑定到任意 Skill；无匹配时回退到基础 Orchestrator
- 单候选 / 近候选 / 弱匹配的选择原因区分

## 6 个 Skill
- question-design
- question-followup
- question-intent
- answer-evaluation
- interview-review
- difficulty-control

## 不做
- 不训练 JEV
- 不放代码 Bug / 回归 / Vibe Coding 治理 Skill
- 不绕过 Harness
- 不让 Skill 直接执行 Tool
