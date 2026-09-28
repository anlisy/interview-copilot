---
name: difficulty-control
description: 根据候选人熟悉度、岗位要求、当前回答表现和本场已覆盖能力控制面试题难度，使难度逐步递进而不是随机跳变。
metadata:
  version: "1.0"
  domain: interview
  signals: [难度, 难度控制, 入门, 中等, 深挖, 高难, 候选人熟悉, 岗位要求, 递进]
  intents: [难度判断, 进阶, 校准]
  allowed_actions: [generate]
---

# 目标
让难度反映“候选人当前可验证能力 + 岗位要求 + 已有证据”，而不是单纯追求困难。

## 适用场景
- 主问题难度规划。
- 根据上一题表现动态调整下一题难度。
- 检查整场难度曲线是否突然跳变。

## 四级难度
- `L1 foundation`：概念和项目事实确认。
- `L2 implementation`：实现机制、调用链、关键代码/配置。
- `L3 design`：架构设计、边界、异常、性能、权衡。
- `L4 challenge`：极端约束、替代方案、反例、跨组件联动。

## 难度输入
- `candidate_familiarity`：简历中是否有直接经历。
- `jd_relevance`：与岗位要求的相关程度。
- `answer_quality`：前一题回答表现。
- `coverage_gap`：本场尚未覆盖的能力。
- `question_history`：已有题目的难度序列。

## 校准规则
1. 有直接项目经历：优先 L2 起步。
2. 只在简历技能列表出现、没有项目证据：优先 L1。
3. 目标岗位的核心能力且前一题回答充分：可升一级。
4. 前一题暴露明显知识缺口：优先保持或降低，不要突然跳到 L4。
5. 连续两题已经是 L3/L4：下一题除非有明确理由，否则回到 L2/L3。
6. 难度变化必须有 reason_code，例如 `answer_strong_upgrade`、`coverage_gap`。

## 输出
```json
{
  "difficulty": "L3",
  "reason_code": "direct_project_plus_jd_core",
  "evidence": ["简历有实际项目", "JD明确要求Agent编排"],
  "max_expected_depth": "architecture_and_tradeoff"
}
```

## 失败处理
- 熟悉度未知：保守使用 L1/L2。
- 历史评分缺失：不要伪造提升或下降理由。
- 岗位不匹配的高难题：优先放弃，而不是为了“难”而难。
