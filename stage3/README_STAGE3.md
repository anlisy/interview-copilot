# Stage 3：Tool Registry + MCP + Tool Policy

## 目标

把“能力”从 Agent 中独立出来：

```text
Skill = 怎么做
Tool  = 现在能做什么
MCP   = Tool 如何标准化暴露/发现
Harness = 最终是否允许执行
```

## 当前 Tool

- `local_rag`
- `nowcoder_search`
- `memory_search`
- `ground_truth_search`（仅用于测试/评测边界；普通 Agent 永远拒绝）

## Agent × Tool × Action 权限

| 调用方 | Tool | 允许 Action | Eval |
|---|---|---|---|
| interviewer | local_rag | diagnose / generate / followup | 允许 |
| interviewer | nowcoder_search | generate | **禁止** |
| interviewer | memory_search | diagnose / generate / followup | 允许 |
| scorer | 无外部 Tool | - | - |
| reviewer | memory_search | review | 允许 |
| evaluation_harness | ground_truth_search | retrieve_ground_truth | 仅受控 Eval |

权限矩阵唯一来源：`agent_runtime/permissions.py`。其中 Agent→Tool、Tool→Agent、Tool→Action、Eval deny/eval only 必须保持一致；MCP Adapter 只能缩小权限，不能扩大中央矩阵。

## 两层概念：授权 vs 可执行

`ToolRegistry` 是运行时 Tool 的目录。默认 `build_default_registry()` 只注册 Tool 元数据、Schema 和权限，不自动伪造 handler；因为实际 Interview Copilot Tool 是通过 MCP Server 接入的。

因此：

```text
policy allowed + handler bound
    -> 可以执行

policy allowed + handler 未绑定
    -> 返回 tool_unavailable
    -> executed=false
    -> 不执行任何 Tool

policy denied
    -> 返回 policy_denied
    -> blocked=true
    -> handler 永远不会被调用
```

这样可以避免“权限正确但执行链没接上”时误把配置问题当成真实 Tool 调用。

## MCP

`smolagents` 支持 `ToolCollection.from_mcp()` 并可显式设置 `structured_output=True`。MCP Host 侧仍保留 ACL / Eval / Schema / Timeout / Retry 边界。

MCP Session 使用：

1. explicit allowlist
2. central Agent ACL
3. central Action ACL
4. central Eval deny/eval only
5. Input Schema
6. Tool execution
7. Output Schema

任何一步不满足都不执行。

### MCP trust boundary

`ToolCollection.from_mcp()` 默认 `trust_remote_code=False`。只有明确审核、明确受信的本地仓库 MCP Server 才在测试入口开启 `trust_remote_code=True`；生产/远程 MCP 保持默认关闭，直到 Server 来源和部署边界经过审核。

## 默认 Registry 与真实 MCP

策略验证：

```bat
python -m stage3.cli --agent interviewer --action generate --tool nowcoder_search
```

这条命令只验证权限；默认 Registry 没有绑定实际 handler，因此不会执行 Tool。

真实 Interview MCP 调用：

```bat
python -m stage3.mcp_interview_cli --agent interviewer --action generate --tool local_rag
```

```bat
python -m stage3.mcp_interview_cli --agent interviewer --action generate --tool nowcoder_search
```

`nowcoder_search` 需要 `NOWCODER_SEARCH_URL` 指向用户拥有/获授权的搜索服务；不会直接爬取站点。

Eval 时：

```bat
python -m stage3.mcp_interview_cli --agent interviewer --eval --action generate --tool nowcoder_search
```

必须被 Tool Policy 在执行前拒绝。

## 安全边界

1. Agent ACL：默认拒绝，没有白名单就不能调用。
2. Action ACL：只要调用方带 `action`，Tool 必须显式声明该 Agent 的 action allowlist。
3. Eval Deny：Eval 模式额外阻断 `nowcoder_search`。
4. Ground Truth：普通 Agent 始终拒绝 `ground_truth_search`，不依赖调用方自觉。
5. MCP Allowlist：严格模式必须显式列出允许加载的 Tool。
6. Schema：调用前和结果后均做结构校验。
7. Timeout：Tool 自带超时；调用可进一步缩短为 session deadline。
8. Retry：只有 `idempotent=true` 的 Tool 才自动重试。
9. Unknown Tool：fail-closed。
10. Handler Missing：不执行、不重试，返回 `tool_unavailable`。
11. MCP Adapter 不能扩大中央权限矩阵。

## 评测隔离

`ground_truth_search` 只允许 `evaluation_harness + retrieve_ground_truth + eval_mode=true + principal_type=evaluator`，普通 Agent 永远拒绝。

## 测试

```bat
python -m pytest stage3\tests -q
```

最终目标是：

```text
Agent
 ↓
Skill
 ↓
Orchestrator
 ↓
Tool selection / MCP discovery
 ↓
Harness / ToolPolicy
 ↓
Tool execution
```

Tool 被发现不代表它可以被调用；Tool 被授权也不代表它已经连接。两个状态必须分别验证。


### Interview MCP CLI 边界

`mcp_interview_cli` 只用于普通 Interview Agent 的 MCP 工具验证，因此只暴露 `interviewer / scorer / reviewer` 与 `local_rag / nowcoder_search / memory_search`。`ground_truth_search` 属于独立的 Eval 能力，不通过普通 Interview MCP Server 暴露。

`local_rag` 的 `category` 默认传空字符串，表示不限定分类；可通过 `--category` 指定分类。`nowcoder_search` 的 `company` / `role` 也默认传空字符串，避免 MCP schema 适配层把可选 Union 参数误判为必填。

### stdio MCP 日志约束

MCP stdio 的 stdout 属于 JSON-RPC 协议流。旧业务 Tool 如果通过 `print()` 输出进度日志，必须在 MCP Server 适配层隔离，否则会污染协议流；业务日志应改用 stderr/logging。

### MCP stdio legacy-tool isolation
Legacy application Tools may still print progress to stdout. Because MCP stdio reserves stdout for JSON-RPC, `local_rag` and `memory_search` now execute legacy code in an isolated child process; stdout is captured there, while timing/debug information is emitted to stderr. Use `python -m stage3.mcp_interview_cli --profile ...` to see host and MCP timing breakdowns.
