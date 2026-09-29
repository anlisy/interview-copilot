# Stage5 Runtime Integration

新增真实 Trace → Evaluation 证据接入层，不改 Stage1~4。

测试：

```bat
python -m pytest stage5\tests -q
```

运行真实 Trace：

```bat
python -m stage5.evaluation.runtime_eval_cli --traces storage\traces --golden stage5\evaluation\golden\interview_eval.jsonl --predictions stage5\evaluation\golden\predictions.sample.jsonl --config stage5\evaluation\eval_config.yaml --output storage\eval\predictions.runtime.jsonl
```
