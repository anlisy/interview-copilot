# Stage6：Decision Layer + JEV Benchmark

## 目标

Stage6 把“有限候选决策”从 Skill/Tool/Intent 的具体实现中抽出来，统一成可替换的 `DecisionEngine`，并用同一份 Benchmark 对比 Rule、智谱 GLM 和 JEV。

核心职责划分：

- Rule：确定性、零模型调用的基线。
- GLM：通过现有智谱 OpenAI-compatible API 做通用决策基线。
- JEV：通过官方 `typesafe-sdk` 的 `Choice` 做 bounded decision。
- Harness：仍然是最终授权者；Decision Layer 只能建议 choice，不能绕过 Agent ACL、Action ACL、Eval ACL。

## 三类决策

1. Skill Router：从候选 Skill 中选择一个。
2. Tool Router：从 `local_rag / memory_search / nowcoder_search / no_tool` 等有限集合中选择一个。
3. Question Intent Judge：判断题目是否属于同一考察意图。

## 运行

先跑纯离线 fixture，验证工程链路：

```bat
python -m stage6.benchmark.cli --mode fixture
```

真实 GLM + JEV：

```bat
set ZHIPU_API_KEY=...
set ZHIPU_MODEL=glm-4-flash
set TYPESAFE_API_KEY=...
set JEV_MODEL=jev-latest
python -m stage6.benchmark.cli --mode real --engine all --output storage\eval\stage6_decision_benchmark.json
```

JEV 官方 Python SDK 当前要求 Python 3.10+，安装包为 `typesafe-sdk`，默认模型为 `jev-latest`；Choice 用于闭集路由/分类，并支持最多 255 个候选。实际 API 使用量按 TypeSafe 官方账户计费，代码把输入/输出单价放在可配置参数中，不把实验结果硬编码。citeturn389612search0turn389612search6turn389612search8

## 置信度策略

Stage6 不把 confidence 直接等价于准确率。先在独立 Validation Set 上调用 `calibrate_thresholds()`，再冻结 Test Set。输出：

- Accuracy
- Macro-F1
- Confusion Matrix
- ECE
- Brier
- P50/P95 Latency
- Input/Output/Total Tokens
- Cost
- Fallback Rate

推荐最终比较：

```text
Rule vs GLM vs JEV
```

而不是预设 JEV 必然更好。

## Stage2 接入

`stage6.integrations.stage2_skill_selector.Stage2DecisionSelector` 可作为 Stage2 `ManagedRuntime(selector=...)` 的注入式 selector，不改变 Stage2 候选 Skill 召回和激活逻辑：

```python
from stage2.agent_runtime.managed_runtime import ManagedRuntime
from stage6.decision.jev import JevDecisionEngine
from stage6.integrations.stage2_skill_selector import Stage2DecisionSelector

runtime = ManagedRuntime(
    orchestrator,
    skills_root,
    selector=Stage2DecisionSelector(JevDecisionEngine()),
)
```

JEV confidence 低于 selector 设置的阈值时只返回 fallback 状态，由上层决定是否交给 GLM/Rule；不会绕过 Harness。

## Fixture 与正式实验

`--mode fixture` 只证明接口、指标和报告链路，不能作为模型效果结论。正式结果必须使用独立 Validation/Test Set，并记录模型版本、数据集版本、时间、Token、延迟和成本。

## JEV transport

The project uses standard-library HTTP by default, so the main venv does not need `typesafe-sdk`. Set `TYPESAFE_API_KEY` and optionally `JEV_MODEL`. The official SDK remains optional.


## Stage6-B

Benchmark reports now distinguish raw decision metrics from effective end-to-end latency/token/cost after fallback. GLM adapters derive a normalized probability vector when a response omits explicit probabilities and mark this in metadata as `probability_source=derived_from_confidence`. changes
- Intent benchmark uses `state.question_a` and `state.question_b` to compare two questions.
- JEV intent instructions are English while the underlying state can remain Chinese.
- Benchmark rows expose `raw_predicted` and `effective_predicted`.
- Metrics include `raw_accuracy`, `effective_accuracy`, `fallback_gain`, `fallback_applied_rate`, fallback latency/tokens/cost.
- Use `--fallback-engine glm` to route low-confidence JEV decisions through GLM in a real benchmark.


### Stage6-B

Benchmark reports now distinguish raw decision metrics from effective end-to-end latency/token/cost after fallback. GLM adapters derive a normalized probability vector when a response omits explicit probabilities and mark this in metadata as `probability_source=derived_from_confidence`. real benchmark

JEV only (raw):
```bat
python -m stage6.benchmark.cli --mode real --engine jev
```

JEV with GLM fallback (effective result):
```bat
python -m stage6.benchmark.cli --mode real --engine jev --fallback-engine glm
```

The report keeps raw and effective outcomes separate. `fallback_gain = effective_accuracy - raw_accuracy`. The Intent dataset uses `state.question_a` and `state.question_b`.

## Stage6-C

Stage6-C adds a validation-only calibration and threshold experiment layer. It does not change the decision engine contract.

Calibration:

```bat
python -m stage6.benchmark.policy_cli --mode real --engine jev
```

With a fallback engine and threshold sweep:

```bat
python -m stage6.benchmark.policy_cli --mode real --engine jev --fallback-engine glm --thresholds 0.50,0.60,0.70,0.80,0.90,0.95
```

The report separates:

- `auto_rate`: confidence above the auto threshold.
- `review_rate`: confidence in the review band.
- `fallback_candidate_rate`: decisions below the review threshold.
- `fallback_applied_rate`: fallback actually executed.
- `effective_*`: latency, total tokens and cost after any executed fallback.

Calibration should be run on an independent Validation Set. The selected policy is then frozen before evaluating the Test Set.

GLM and JEV cost rates are configurable through `GLM_INPUT_COST_PER_1M`, `GLM_OUTPUT_COST_PER_1M`, `JEV_INPUT_COST_PER_1M`, and `JEV_OUTPUT_COST_PER_1M` (or constructor arguments). A zero GLM cost means pricing has not been configured and must not be interpreted as free service.


### Stage6-C: calibration / threshold sweep / frozen Test Set

Validation calibration and Test evaluation are explicitly separated:

```bat
python -m stage6.benchmark.policy_cli --mode real --engine jev --fallback-engine glm \
  --validation-dataset stage6\datasets\decision_validation.jsonl \
  --test-dataset stage6\datasets\decision_test.jsonl
```

The command first calibrates `auto_threshold` and `review_threshold` on Validation, sweeps candidate thresholds, then freezes the chosen policy and evaluates Test without recalibration. The report contains `auto_rate`, `review_rate`, `fallback_candidate_rate`, `fallback_applied_rate`, effective latency/token/cost, reliability bins, ECE/Brier, and pricing configuration.

For real GLM experiments, set `GLM_INPUT_COST_PER_1M` and `GLM_OUTPUT_COST_PER_1M`; for JEV, `JEV_INPUT_COST_PER_1M` and `JEV_OUTPUT_COST_PER_1M` are supported. A zero GLM cost means pricing was not configured.


## Cost units

Cost is only directly comparable when the currency is known and the same across engines. Decision engines expose `pricing_currency` in metadata. GLM is configured as CNY in this project (`GLM_PRICE_CURRENCY=CNY`); JEV defaults to `UNSPECIFIED` until its vendor currency is verified.
