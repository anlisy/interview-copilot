# 阶段 5：Evaluation / Golden Set / Regression Gate

## 目标

把原来的“Top-1 语义命中率 + 0.55 阈值”升级为可解释、可重复、可回归的 Agent 评测层。

## 设计原则

1. Golden Set 是评测真值，不直接把向量检索结果当答案。
2. Validation Set 用来校准阈值，Test Set 只用于最终报告。
3. 评测覆盖 Retrieval、Question、Answer、Agent、Memory、Safety、Performance。
4. 门禁同时支持绝对阈值和相对基线回归。
5. Stage5 不调用本地模型，也不改变 Stage1~4 的运行时。

## 第一版交付

- Golden Case schema
- Retrieval：Recall@5 / Precision@5 / MRR / nDCG@5
- Question：Intent Match / Topic Coverage / Duplicate Rate / Groundedness
- Answer：Rubric Coverage / Unsupported Claim Rate
- Agent：Tool Selection Accuracy / Invalid Tool Call Rate / Trajectory Success Rate / Retry Rate / Max-step Hit Rate
- Memory：Recall@5 / Temporal State Accuracy / Stale Memory Rate / Unsupported Memory Rate
- Safety：Ground Truth Leakage / Unauthorized Tool Call / Prompt Injection Bypass
- Performance：P50 / P95 Latency / Average Tokens / Average Cost
- Validation threshold calibration
- Regression gate
- CLI JSON report

正式项目应继续扩充 Golden Set，并使用人工标注的 Validation/Test 数据替换示例数据。
