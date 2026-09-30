# Stage8-C

## 目标
完成真实 Agent Runtime、Stage1 状态桥接以及在线 Memory Candidate Capture，使 Stage8 从模块集成门面进入可运行的在线闭环。

## 完成项

- Stage6 Skill / Tool / Intent 并行决策。
- 在线概率-Choice 一致性校正。
- Stage4 Context Manager 接入在线工作集。
- Stage1 Interviewer / Scorer / Reviewer 适配器。
- 旧 Stage1 Prompt 无需改接口即可接收 Stage8 Context。
- SessionState ↔ InterviewState State Bridge。
- 用户回答候选记忆自动识别 + 显式标记。
- Raw Trajectory → Stage7-A/B Consolidation。
- Session Finish 后进入 FINISHED。
- 测试覆盖状态桥、Context 注入、Memory Candidate、Consolidation。

## 测试命令

```cmd
python -m pytest -q stage8\tests
python -m pytest -q
```


## 最终收口

- FINISHED 终态幂等：重复 finish 不增加 turn、不重新 Decision/Agent/Stage7。
- FINISHED 拒绝普通新请求。
- 显式 Agent/Action 与 Decision Layer 建立执行合同，冲突时记录 mismatch，由显式执行合同决定实际 Skill。
- RouteResult 增加 decision_route / fallback_applied 推荐语义，保留 route / fallback 兼容。
- last_memory_capture / last_consolidation / last_turn_id 持久化。
- Stage8-C 独立测试：18 passed（当前构建验证环境）。
