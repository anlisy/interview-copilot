# Stage 1 落地说明

本阶段把现有 Interview Copilot 通过兼容层接入中心 Agent Runtime。

核心链路：

`Goal + State + Observations -> Zhipu Orchestrator -> Decision(JSON) -> Harness -> Existing Supervisor Handler -> Trace`

新增：

- `zhipu_client.py`：直接调用智谱 API，不部署本地模型。
- `HarnessContext.session_version`、step/followup/token/cost/deadline。
- Agent / Action / Tool ACL。
- Eval 禁用 ground-truth / nowcoder 等工具。
- Workflow 合法状态迁移检查。
- Action result schema，并兼容 dataclass / Mapping / Pydantic。
- 结构化 JSONL Trace，并对简历、JD、回答等敏感字段做摘要哈希。
- Orchestrator 决策字段与授权校验。
- Runtime 模式下诊断、出题、评分、复盘均经过 Harness；复盘最终进入 `FINISHED`。

## 已验证

当前包内测试：`22 passed`。

另外用本地模拟 OpenAI-compatible HTTP Server 做过完整 CLI 冒烟，以下两种启动方式均通过：

```bat
python -m stage1.cli
python stage1\cli.py
```

并完成：

`INIT -> DIAGNOSIS -> ASKING -> SCORING -> REVIEWING -> FINISHED`

## 运行

```bat
cd /d C:\Users\Albert\interview-copilot
venv\Scripts\activate
set ZHIPU_API_KEY=你的Key
set ZHIPU_MODEL=glm-4-flash
set ZHIPU_BASE_URL=https://open.bigmodel.cn/api/paas/v4
set AGENT_ORCHESTRATOR=1
python -m stage1.cli
```

不要把 Key 写入 Git。
