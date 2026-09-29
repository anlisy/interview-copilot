# Stage6

- DecisionEngine：统一 Rule / GLM / JEV。
- Benchmark：Skill / Tool / Intent 三类决策。
- Metrics：质量 + 校准 + 延迟 + Token + Cost + Fallback。
- Integration：可注入 Stage2 ManagedRuntime。

## Stage6-C v3

Validation 输出 Frozen Policy；Test 只能读取 `--policy-file`，禁止重新校准。
