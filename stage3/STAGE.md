# 阶段 3：Tool / MCP Runtime

## 目的
把外部能力从 Agent 代码中解耦，形成统一 Tool Registry、ACL、Schema、Timeout、Retry、Audit 边界。

## 验收

- Tool Registry 可注册 / 查询 / 绑定 handler。
- Agent ACL 默认拒绝。
- Eval 模式禁止 `nowcoder_search`。
- Ground Truth Tool 对普通 Agent 永远拒绝。
- Tool 输入输出都经过 schema 校验。
- 非幂等 Tool 不自动重试。
- 幂等 Tool 在临时异常时可重试。
- Tool timeout 不阻塞调用方。
- MCP loader 显式启用 structured output。

## Stage 3 第二部分：真实 MCP 生命周期

- `mcp_runtime.py`：在保持 MCP ToolCollection 生命周期的前提下，把发现到的 MCP Tool 转换为受控 ToolRegistry。
- `mcp_servers/interview_mcp_stdio.py`：stdio MCP 入口，供 `smolagents` 通过子进程管理生命周期。
- `mcp_servers/integration_mcp.py`：确定性集成测试服务器，不依赖真实外部数据源。
- `mcp_cli.py`：真实 discovery -> registry -> policy -> schema -> call -> structured output 冒烟入口。
- `requirements-mcp.txt`：在现有 `smolagents==1.26.0` 环境中补装 MCP extra。

真实 MCP 连接显式启用 `structured_output=True`；官方文档说明该模式支持 `outputSchema` 与 structuredContent，并建议在 MCP 生命周期内使用 context manager。citeturn576893search0turn878208search4

## Agent × Tool × Action 权限矩阵

当前默认最小权限如下：

| 调用方 | Tool | 允许 Action | Eval 模式 |
|---|---|---|---|
| interviewer | local_rag | diagnose / generate / followup | 允许 |
| interviewer | nowcoder_search | generate | 禁止 |
| interviewer | memory_search | diagnose / generate / followup | 允许 |
| scorer | 无 | - | - |
| reviewer | memory_search | review | 允许 |
| evaluation_harness | ground_truth_search | retrieve_ground_truth | 仅受控 Eval |

`scorer` 当前只接收 question / answer / rubric，因此默认不开放外部 Tool；后续若确有业务需求再增加最小权限，而不是先放开。

Tool 被发现并不代表可以调用：MCP Host 必须同时通过显式 allowlist、Agent ACL、Action ACL 和 Eval 策略；Agent 看见的 Tool 列表也会先经过 `ToolPolicy.visible_tools()` 过滤，执行时 `ToolExecutor` 再做一次 fail-closed 校验。
