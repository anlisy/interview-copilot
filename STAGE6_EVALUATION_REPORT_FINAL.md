# Interview Copilot Stage6 Decision Layer：实验与结论汇总

## 1. 实验范围

Stage6 目标是把 Skill Router、Tool Router、Question Intent Judge 从“生成式大模型直接判断”拆成独立 Decision Layer，并比较三类决策引擎：

- Rule：确定性规则基线，0 token。
- GLM：智谱大模型，承担有限集合选择。
- JEV：专用有限选择/判别引擎，返回 choice / probabilities / confidence。

运行链路统一记录 raw result 与 effective result，并统计准确率、Macro-F1、置信度校准、P50/P95 延迟、输入/输出/总 Token、成本以及 fallback 的收益/代价。

## 2. 数据集与证据等级

### 2.1 小型真实 API 对比集

Stage6-B 使用 12 条真实 API benchmark case，用于早期工程选型和 fallback 验证。样本量较小，不用于最终泛化结论。

### 2.2 正式 Stage6 数据集

正式数据集共 110 条，当前生成状态为 `synthetic_template`，必须人工复核后才能作为最终 Ground Truth：

| 类型 | 总数 | Validation | Test |
|---|---:|---:|---:|
| Skill | 30 | 15 | 15 |
| Tool | 30 | 15 | 15 |
| Intent | 50 | 25 | 25 |
| 合计 | 110 | 55 | 55 |

具体分布：

- Skill：6 个 Skill，各 5 条。
- Tool：local_rag 8、memory_search 8、no_tool 7、nowcoder_search 7。
- Intent：same_intent 25、different_intent 25。
- Validation/Test 按 task_type + expected label 分层抽样。

重要限制：正式数据中的 `rule_keywords` 是为 Rule baseline 提供的元数据，因此 Rule 在这套数据上的满分不代表真实场景泛化能力。

## 3. Rule / GLM / JEV 核心指标

### 3.1 Rule：正式 110 条基线

对当前 110 条 synthetic-template 数据运行 Rule baseline：

| 指标 | Overall | Skill | Tool | Intent |
|---|---:|---:|---:|---:|
| Accuracy | 100.00% | 100.00% | 100.00% | 100.00% |
| Token | 0 | 0 | 0 | 0 |

解释：这是确定性规则基线，不应把 100% 当作真实质量证据。原因是测试样本本身携带 `rule_keywords`，存在明显规则泄漏。它的主要价值是作为零 Token、确定性、可解释的工程基线。

### 3.2 GLM：早期 12 条真实 API benchmark

| 指标 | Overall | Skill | Tool | Intent |
|---|---:|---:|---:|---:|
| Accuracy | 75.00% | 100.00% | 100.00% | 25.00% |
| Macro-F1 | 84.00% | — | — | — |
| P50 latency | 3126 ms | — | — | — |
| P95 latency | 4513 ms | — | — | — |
| Avg total tokens | 215.0 | — | — | — |
| Cost | 未配置 | 未配置 | 未配置 | 未配置 |

该结果只能作为小样本真实 API 对比，不应外推到一般场景。

### 3.3 JEV：早期 12 条真实 API benchmark

| 指标 | Overall | Skill | Tool | Intent |
|---|---:|---:|---:|---:|
| Accuracy | 91.67% | 100.00% | 100.00% | 75.00% |
| Macro-F1 | 94.67% | — | — | — |
| P50 latency | 约 862 ms | — | — | — |
| 早期 P95 | 约 1.06 s | — | — | — |
| Avg total tokens | 460.75 | — | — | — |
| Avg cost | 约 1.742e-05（JEV 价格单位；币种未在当前项目资料中确认）/次 | — | — | — |

JEV 的重复运行中 P95 有过约 3.3 s 的波动，因此延迟结论应使用多次运行的 P50/P95 统计，而不是一次运行的单点值。

## 4. GLM 作为低置信 fallback 的实验

### 4.1 12 条小型真实 API benchmark

测试“JEV 低置信 → GLM fallback”的策略：

- Raw JEV accuracy：91.67%
- Effective accuracy：75.00%
- Fallback gain：-16.67 percentage points
- Intent raw accuracy：75%
- Intent effective accuracy：25%

结论：在该实验上，GLM fallback 没有救回 JEV 的低置信错误，反而显著降低整体准确率。

### 4.2 55 条 Validation 的正式阈值 Sweep

当前 v4 使用候选阈值：0.50 / 0.60 / 0.70 / 0.80 / 0.90 / 0.95。

| Threshold | Effective Accuracy | Raw Accuracy | Fallback Gain | Auto Rate | Review Rate | Fallback Candidate | P50 ms | P95 ms | Avg Total Tokens | Effective Avg Cost（价格单位未统一） |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.50 | 94.55% | 98.18% | -3.64 pp | 85.45% | 10.91% | 3.64% | 851.3 | 1037.5 | 511.31 | 不报告（币种未统一） |
| 0.60 | 92.73% | 98.18% | -5.45 pp | 85.45% | 9.09% | 5.45% | 853.6 | 1553.2 | 515.15 | 不报告（币种未统一） |
| 0.70 | 92.73% | 98.18% | -5.45 pp | 81.82% | 3.64% | 14.55% | 856.6 | 3122.2 | 534.71 | 不报告（币种未统一） |
| 0.80 | 90.91% | 98.18% | -7.27 pp | 74.55% | 9.09% | 16.36% | 858.1 | 3140.2 | 538.65 | 不报告（币种未统一） |
| 0.90 | 89.09% | 98.18% | -9.09 pp | 65.45% | 16.36% | 18.18% | 866.7 | 3140.2 | 542.45 | 不报告（币种未统一） |
| 0.95 | 87.27% | 98.18% | -10.91 pp | 58.18% | 21.82% | 20.00% | 866.7 | 3392.4 | 546.29 | 不报告（币种未统一） |

这一组结果提供了比 12 条样本更稳定的方向性证据：随着 threshold 提高，fallback 被触发得更多，但 effective accuracy 继续下降，P95 延迟明显升高，成本也上升。

## 5. Stage6-C v4 Calibration

Validation 55 条，当前冻结策略：

- auto_threshold = 0.50
- review_threshold = 0.30
- threshold_candidates = [0.50, 0.60, 0.70, 0.80, 0.90, 0.95]
- selected_from_candidates = true
- auto_accuracy = 100.00%
- auto_coverage = 89.09%
- constraints_satisfied = true

这里的 `auto_accuracy=100%` 指“被自动放行的子集”的准确率，不等于整个 Validation Set 的 effective accuracy。

## 6. Frozen Test 最终结果

55 条 Test，只读取 Validation 冻结策略：

| 指标 | 最终结果 |
|---|---:|
| Accuracy | 98.18% |
| Macro-F1 | 99.33% |
| Raw Accuracy | 98.18% |
| Effective Accuracy | 98.18% |
| Raw Macro-F1 | 99.33% |
| Effective Macro-F1 | 99.33% |
| ECE | 0.0700 |
| Brier | 0.0245 |
| P50 latency | 853.819 ms |
| P95 latency | 1282.711 ms |
| Avg input tokens | 451.33 |
| Avg output tokens | 51.35 |
| Avg total tokens | 502.67 |
| Effective avg total tokens | 502.67 |
| Avg cost | 1.896e-05（按当前 JEV 计价配置的价格单位）/次 |
| Effective avg cost | 1.896e-05（按当前 JEV 计价配置的价格单位）/次 |
| Fallback applied | 0 |
| Fallback rate | 0 |
| Auto rate | 98.18% |
| Review rate | 1.82% |

### 6.1 Test 按任务类型

由 55 条 Test 的混淆矩阵可直接得到：

| Task Type | Correct | Total | Accuracy |
|---|---:|---:|---:|
| Skill | 15 | 15 | 100.00% |
| Tool | 15 | 15 | 100.00% |
| Intent | 24 | 25 | 96.00% |
| Overall | 54 | 55 | 98.18% |

唯一错误来自 Intent：`same_intent → different_intent` 1 条。

## 7. 当前方案为什么是 JEV + 阈值路由，而不是 GLM 主决策

### 7.1 任务形态匹配

Stage6 Router 本质上是有限集合选择：Skill / Tool / Intent 都是 closed-set decision。JEV 原生输出 choice + probability/confidence，天然适合这个问题；GLM 更偏通用生成，不是专门的有限集合判别器。

### 7.2 小样本真实 API 对比

12 条 benchmark 中：

- JEV：91.67%
- GLM：75.00%
- Rule：100%（但该规则基线存在明显模板泄漏）

JEV 的 P50 约 0.86 s，而 GLM P50 约 3.13 s；早期 P95 也明显低于 GLM。

### 7.3 正式 55 条 Test

冻结策略下 JEV 达到 98.18% accuracy / 99.33% Macro-F1，且只发生 1 条 Intent 错误；本次 Test 没触发 GLM fallback，因此有效结果与 raw 结果相同。

### 7.4 GLM fallback 不具备当前默认启用的证据

12 条实验：fallback gain = -16.67 pp。

55 条 Validation Sweep：所有测试 threshold 的 fallback gain 都为负，而且 threshold 越高，fallback rate、P95、成本整体上升。

因此当前实验更支持：

> JEV 作为主决策器；低置信样本进入 review/人工或后续专门校准策略，而不是默认直接交给 GLM 重新决定。

这不是“GLM 永远不能做 fallback”的证明，只能说明当前 Prompt、阈值和评测集下，没有证明 GLM 作为低置信决策器有效。

## 8.1 成本口径修正

当前项目成本字段表示“按配置的每百万 Token 单价计算出的数值”。成本能否直接比较还取决于计价币种是否一致；原报告把 JEV 的数值直接标成 USD，但当前资料不足以支持这一币种判断，因此这里撤销 USD 标注。

- JEV：当前配置为 `0.042 / 1M input token`、`0 / 1M output token`，**币种在当前项目资料中未确认**。
- GLM：本项目采用 `0.1 元 / 1M input token`、`0.1 元 / 1M output token` 的配置，即按人民币计价。
- 因而在确认 JEV 币种前，不能直接做 JEV 与 GLM 的跨币种成本比较。
- 后续报告应分别记录 `input_cost_per_million`、`output_cost_per_million`、`currency`，而不是只保存一个裸 `cost`。

当前 Frozen Test 的 JEV 平均 Token 为 451.33 input + 51.35 output；按现有 JEV 配置得到的 1.896e-05 只是该配置下的**价格单位/次**，不应再写成 USD。若将 GLM 按项目配置的 0.1 元 / 1M input + 0.1 元 / 1M output 计算，则 502.67 的平均总 Token 对应约 5.03e-05 元/次；但这不能与币种未确认的 JEV 价格单位直接相加或比较。

## 8. 当前结果中必须保留的限制

1. 110 条正式数据目前是 `synthetic_template` 的语义复核候选版，仍保留 `human_signoff_required=true`，因此 98.18% 不能写成真实生产泛化准确率。
2. Rule 100% 受 `rule_keywords` 元数据影响，不能作为模型质量上限。
3. GLM/JEV 的早期 12 条 benchmark 样本量很小，只适合方向性选型。
4. JEV confidence 在不同运行中存在波动，因此需要人工复核后的 Hard Case 数据和重复运行稳定性测试。
5. 当前 Calibration 优化的是“auto accuracy + auto coverage”，而 Threshold Sweep 展示的是“整个 Validation 的 effective accuracy”。两者目标不同；当前 0.50 是满足现有 Calibration 契约的候选，不应描述成“全局最优阈值”。

## 9. 当前阶段可以支撑的结论

可以较有把握地写：

- Decision Layer 中，JEV 在当前 finite-choice 路由任务上的 API 实测优于本阶段 GLM 小样本 benchmark。
- 当前 55 条冻结 Test 中，JEV 达到 98.18% accuracy / 99.33% Macro-F1；Skill 与 Tool 各 100%，Intent 为 96%。
- 在当前实验条件下，GLM 低置信 fallback 没有带来正向 accuracy gain，反而增加延迟和成本，因此当前默认方案不启用自动 GLM rescue。
- Rule 可以作为零 Token 的确定性基线和兜底，但当前正式数据存在规则泄漏，不能据此证明 Rule 泛化能力。

不能写成：

- “JEV 泛化准确率已经达到 98.18%”。
- “GLM 一定不适合作为 fallback”。
- “0.5 是经过最终验证的全局最优阈值”。
