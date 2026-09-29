# Agent Eval 规范

## Golden Case 最小字段

- `id`
- `canonical_question`
- `question_intent`
- `relevant_ids`
- `graded_relevance`
- `required_concepts`
- `required_topics`
- `disallowed_claims`
- `expected_tool`
- `expected_memory_ids`

## Prediction 最小字段

- `id`
- `ranked_ids`
- `observed_concepts`
- `covered_topics`
- `question_intent`
- `is_duplicate`
- `grounded`
- `unsupported_claims`
- `tool_selected`
- `invalid_tool_call`
- `trajectory_success`
- `retried`
- `max_step_hit`
- `latency_ms`
- `tokens`
- `cost`
- `memory_ids`
- `temporal_state_ok`
- `stale_memory`
- `unsupported_memory`
- `ground_truth_leakage`
- `unauthorized_tool_call`
- `prompt_injection_bypass`

## 指标

### Retrieval

Recall@K、Precision@K、MRR、nDCG@K。

### Question

Intent Match、Topic Coverage、Duplicate Rate、Groundedness。

### Answer

Rubric Coverage、Unsupported Claim Rate。

### Agent

Tool Selection Accuracy、Invalid Tool Call Rate、Trajectory Success Rate、Retry Rate、Max-step Hit Rate。

### Memory

Memory Recall@K、Temporal State Accuracy、Stale Memory Rate、Unsupported Memory Rate。

### Safety

Ground Truth Leakage、Unauthorized Tool Call、Prompt Injection Bypass。

### Performance

P50 / P95 latency、tokens/session、cost/session。

## 门禁

门禁是工程约束，不是“模型质量真理”。建议同时检查：

- absolute：低于最低标准直接失败；
- relative：相对 baseline 回退超过允许范围直接失败；
- safety：安全类指标默认不可回退到非零。
