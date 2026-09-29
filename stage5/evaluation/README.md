# Stage5 Evaluation

## 运行

```bat
python -m stage5.evaluation.eval_cli ^
  --golden stage5\evaluation\golden\interview_eval.jsonl ^
  --predictions stage5\evaluation\golden\predictions.sample.jsonl ^
  --config stage5\evaluation\eval_config.yaml
```

指定 baseline 做回归：

```bat
python -m stage5.evaluation.eval_cli ^
  --golden stage5\evaluation\golden\interview_eval.jsonl ^
  --predictions stage5\evaluation\golden\predictions.sample.jsonl ^
  --baseline stage5\evaluation\golden\baseline.sample.json ^
  --config stage5\evaluation\eval_config.yaml
```

## 数据关系

Golden Case = 人工标注真值。

Prediction = Agent 实际运行结果。

Baseline = 上一个版本已经固化的评测结果，而不是另一套“理论标准”。

## 阈值

不要把 0.55、0.8、0.9 解释成理论常数。`threshold_calibrator.py` 仅对 Validation Set 做 F1 校准。

独立 Test Set 不参与校准。
