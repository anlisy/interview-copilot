# Stage6 正式数据集语义复核记录

## 结论

逐条检查 110 条唯一样本后，**没有发现需要直接修改 `expected` 的明显错标**。原始输入、选项和标签保持不变，因此此前 Validation/Test 的数值不会因这次“仅增加审核元数据”而改变。

但这不是“人类签字后的 Ground Truth”。以下 16 条样本存在更明显的语义边界，应由项目作者做最终确认。

- `intent-04`：同一主题，但“压力来源/集群影响”的抽象层级接近，建议人审确认是否归为同一意图。
- `intent-06`：对比 Redis 与 MySQL 的选型收益，和缓存收益高度相关，建议确认粒度定义。
- `intent-14`：Memory 与 Redis 的职责边界属于架构概念，需确认标注标准是否稳定。
- `intent-17`：Validation/Test 独立性属于评测方法论概念，需确认与“最终效果报告”是否保持同一意图。
- `intent-19`：Tool Output 不可信与“不允许修改系统规则”紧密相关，属于安全原则近邻样本。
- `intent-23`：原始轨迹作为源真相与长期 Memory 不替代原始轨迹逻辑高度重合，建议人审。
- `intent-27`：重复消费“为什么发生”和“发生以后如何幂等”边界清晰，但属于同一主题近邻。
- `intent-34`：QueryID 的作用与幂等性设计有关联，需确认本项目 Intent 定义是否区分“作用”和“实现”。
- `intent-38`：Memory/Redis 职责与 Context Token 压缩属于不同层面，但共享同一上下文治理主题。
- `intent-44`：禁用 Ground Truth 与构造 Golden Question 都属于评测数据治理，但动作目标不同。
- `intent-47`：源真相治理原则与文件存储格式是不同维度，建议人审确认。
- `intent-48`：来源字段价值与 Session 索引属于不同层面，但语义较近。
- `intent-50`：工具集合约束与新增 MCP Tool 注册属于治理与注册流程两个维度。
- `skill-11`：question-intent 与其他 Skill 存在边界，需要确认“判断考察方向”确实不应落到 follow-up。
- `tool-03`：“简历中的技术细节”也可能已经位于当前上下文；本样本的标签依赖“需要查询本地材料”的隐含前提。
- `tool-24`：no_tool 的成立依赖“当前上下文已经足够”，需要在实际 runner 语境中保持该前提。

## 数据完整性检查

- ID 唯一。
- Skill / Tool / Intent 三类比例保持 30 / 30 / 50。
- Validation / Test 仍为 55 / 55，按 task_type + expected 分层。
- 未修改任何 `state`、`options`、`expected`，只增加 `review` 元数据。
- `rule_keywords` 继续保留，仅用于 Rule baseline；不能把 Rule 的 100% 解释成泛化能力。

## 最终口径

`status=assistant_reviewed_candidate`；`human_signoff_required=true`。在没有人类复核签字前，报告中继续称其为 `synthetic_template` / `engineering benchmark candidate`，不能写成真实生产泛化 Ground Truth。
