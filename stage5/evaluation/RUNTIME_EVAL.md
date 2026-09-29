# Stage5 运行时证据接入

Stage5 的语义指标继续由 Golden Set + prediction/标注结果提供；运行时指标直接从 Stage1 `storage/traces/*.jsonl` 提取。

## 运行方式

```bat
python -m stage5.evaluation.runtime_eval_cli ^
  --traces storage\traces ^
  --golden stage5\evaluation\golden\interview_eval.jsonl ^
  --predictions stage5\evaluation\golden\predictions.sample.jsonl ^
  --config stage5\evaluation\eval_config.yaml ^
  --output storage\eval\predictions.runtime.jsonl
```

默认用 Golden Case 的 `id` 作为 trace session_id。两者不一致时提供：

```json
{"case_001": "real-session-001", "case_002": "real-session-002"}
```

然后增加 `--session-map path.json`。

## 证据优先级

`tool_selected / trajectory / retry / step / latency / tokens / cost / memory_ids / safety` 等运行时字段由 Trace 覆盖 prediction 中的旧值；语义字段仍来自 prediction/标注，避免 sample 数据冒充真实运行结果。
