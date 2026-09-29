# Stage 4：分层记忆 + Context Manager

## 目标
把“会话状态”和“长期记忆”彻底分层，并让每次模型调用只拿到 token 预算内、与当前任务相关的工作集。

## 四层职责

- Redis：只保存当前 Session 热状态，例如 stage、current question、last turn、计数器和短摘要；不保存完整历史。
- Raw Trajectory：每轮事实写入 JSONL，同时生成 Markdown 可读轨迹。
- Durable Memory：从轨迹中抽取需要长期保留的项目事实、能力事实、面试偏好等，并保存 `source/time/turn/confidence/status` 元数据。
- Recall：BM25 + 可插拔 VectorIndex，通过 RRF 融合；没有向量后端时安全降级为 BM25，不伪造向量结果。

## ReMe-like 生命周期

`capture -> index -> consolidate -> recall`

Stage4 不训练模型，也不新增本地模型服务。向量层只定义接口，后续可接现有向量库或智谱 embedding 服务。

## Context Manager

输入包括系统契约、Workflow、Skill、画像、工作记忆、最近对话、检索证据、当前任务。组件通过 `TokenCounter` 计算输入 token，扣除 output reserve 后进行优先级打包；不会使用“字符数 × 4”作为正式预算规则。

当前没有安装 `tiktoken` 时才使用明确标记为 fallback 的保守估算器。生产环境建议通过 requirements 安装 tokenizer，并可替换为与你的目标模型对应的 tokenizer。
