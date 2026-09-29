# Stage 3 MCP Server

工具：

- `local_rag`：本地知识库检索。
- `nowcoder_search`：调用用户自己提供/获授权的搜索服务。
- `memory_search`：长期面试记忆检索。

Ground Truth / gold answers 不由普通 MCP Server 暴露；评估时通过 Host 侧 Tool Policy 再次阻断，避免只依赖服务端约束。

当前 `smolagents` MCP 加载显式使用 `structured_output=True`，与当前文档推荐的 MCP structured output 能力保持一致。citeturn487184search0
