---
name: question-intent
description: 判断面试问题真正考察的意图，并区分相同主题下的原理、原因、方案、优化、故障、源码、权衡等不同问题，防止向量相似度把不同意图误判为重复。
metadata:
  version: "1.0"
  domain: interview
  signals: [问题意图, intent, 原理, 原因, 方案, 优化, 故障, 源码, 权衡, 对比, 为什么, 怎么解决]
  intents: [原理, 原因, 方案, 优化, 故障, 源码, 权衡, 对比, 设计, 验证]
  allowed_actions: [generate]
---

# 目标
把“主题相似”与“考察意图相同”分开。该 Skill 是问题理解层，不负责生成完整题目。

## 适用场景
- 对待生成或已生成的面试题做 intent 分类。
- 判断两个高语义相似问题是否真的重复。
- 为后续 RAG rerank 或 JEV 决策提供结构化标签。

## 标准意图
- `principle`：解释机制、工作原理。
- `cause`：分析为什么发生、根因是什么。
- `solution`：给出解决方案或架构方案。
- `optimization`：说明性能、成本或稳定性优化。
- `failure`：分析故障、异常、降级。
- `source`：源码、框架实现、底层调用链。
- `tradeoff`：比较多个方案的收益、代价和适用边界。
- `comparison`：明确比较两个方案或技术。
- `design`：从约束出发完成系统设计。
- `verification`：如何证明方案正确、如何压测或验证。

## 判断顺序
1. 找出问题的核心谓词：解释、为什么、如何设计、如何优化、出了问题怎么办、源码怎么实现等。
2. 找出问题对象：Redis、Kafka、Agent、状态机、RAG等。
3. 判断候选回答需要提供什么证据。
4. 输出单一主 intent，可选一个 secondary intent。

## 相似问题处理
例如：
- “Redis 缓存击穿是什么原理？” → `principle`
- “为什么会发生缓存击穿？” → `cause`
- “缓存击穿怎么治理？” → `solution`
- “高 QPS 场景怎么优化击穿治理？” → `optimization`
- “Redis 挂掉后怎么办？” → `failure`

虽然这些问题主题都可能高度相似，但不应仅凭 embedding 相似度合并。

## 与检索的关系
RAG/向量检索负责召回候选证据；本 Skill 负责在候选问题或证据中判断 intent。不要用 intent judge 代替大规模 ANN/BM25 召回。

## 输出
```json
{
  "intent": "tradeoff",
  "secondary_intent": "design",
  "topic": "agent-orchestration",
  "confidence": 0.93,
  "reason_code": "explicit_tradeoff_marker",
  "evidence": ["为什么选择", "相比", "代价"]
}
```

## 失败处理
- 题目同时包含多个等权意图：选择最需要候选人回答的那个作为主意图，其余作为 secondary。
- 无法判断：返回 `unknown`，不得强行编造高置信度。
