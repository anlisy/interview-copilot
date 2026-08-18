# 🎯 Interview Copilot —— 基于多 Agent 的 AI 模拟面试系统

模拟真实面试全流程的 AI 系统：输入简历与 JD，由多个隔离的 Agent 协作完成简历诊断、动态出题、层层追问与评分复盘，并基于真实面经量化评估预测命中率。前后端分离，支持 Web 与 CLI 双入口及跨平台一键部署。

---

## 📖 项目介绍

一般 AI 面试工具只是"调用大模型出几道题"，存在三个问题：出题不贴合个人真实经历、无法层层追问、无法验证"出的题像不像真实面试"。本项目针对性地解决这些问题：

- **多 Agent 隔离**：出题、评分、复盘由三个独立 Agent 完成，出题者看不到评分逻辑，避免自评偏差。
- **动态追问**：面试官 Agent 根据回答深度自主决策是否追问，层层递进深挖，模拟真实压力面。
- **命中率评估**：用真实面经作为 ground truth，量化评估系统预测题命中真实面试题的比例，形成可迭代的优化闭环。
- **检索增强出题**：出题时从向量知识库检索真实面经/八股，让题目贴近真实高频题而非模型瞎编。

### 核心功能

| 功能 | 说明 | 入口 |
|------|------|------|
| 模拟面试 | 诊断→出题→答题→追问→评分→复盘全流程 | Web / CLI |
| 简历诊断 | 分析简历亮点、风险、追问预判 | Web / CLI |
| 面试题预测 | 按题型精确数量出题 + 预判追问，生成问题清单 | CLI |
| 答题助手 | RAG 检索知识库生成参考答案 | CLI |
| 命中率评估 | 对比真实面经量化预测准确度 | API / CLI |

---

## 🏗️ 项目架构

```
                Web (Streamlit)  /  CLI
                        │
                        ▼
              FastAPI 后端 (api.py)
                        │
        ┌───────────────┼────────────────┐
        │        Supervisor 状态机         │  ← 编排面试流转，校验状态迁移
        │  (agents/supervisor.py)          │
        └───────────────┬────────────────┘
        ┌───────────────┼────────────────┐
        ▼               ▼                ▼
 InterviewerAgent   ScorerAgent    ReviewerAgent
 出题/追问/诊断        评分            复盘
   (各持独立模型，评估隔离)
        │
        ▼
  ┌──────────────────────────────────┐
  │  知识库 RAG (ChromaDB + 智谱embedding)  │  ← 检索增强出题
  │  会话持久化 (Redis，可降级内存)          │  ← 状态/行为分离
  │  命中率 Eval (面经做 ground truth)      │  ← 可量化评估
  └──────────────────────────────────┘
```

### 目录结构

```
interview-copilot/
├── agents/              # Agent 层
│   ├── base.py          # Agent 基类（模型路由）
│   ├── interviewer.py   # 面试官 Agent（出题/追问/诊断）
│   ├── scorer.py        # 评分 Agent
│   ├── reviewer.py      # 复盘 Agent
│   ├── supervisor.py    # 状态机调度层
│   └── session_manager.py  # 会话管理（Redis/内存）
├── core/
│   ├── config.py        # 配置（API Key、模型路由）
│   ├── llm.py           # 模型封装 get_model
│   ├── embedding.py     # 智谱 embedding 封装
│   ├── state.py         # 面试状态机定义
│   └── models.py        # 数据模型
├── tools/               # 工具层
│   ├── question_tools.py    # 出题（两步出题+去重）
│   ├── score_tools.py       # 评分
│   ├── review_tools.py      # 复盘
│   ├── followup_tools.py    # 追问决策
│   ├── diagnose_tools.py    # 简历诊断
│   ├── knowledge_tools.py   # 知识库入库/检索
│   ├── eval_tools.py        # 命中率评估
│   ├── predict_tools.py     # 面试题预测
│   └── answer_tools.py      # 答题助手
├── prompts/             # 所有 prompt 模板
├── data/knowledge/      # 知识库源文件（md）
├── tests/               # 测试（50+ 用例，mock 隔离 LLM）
├── api.py               # FastAPI 后端入口
├── app.py               # Streamlit 前端入口
├── cli.py               # 模拟面试 CLI
├── cli_predict.py       # 面试题预测 CLI
├── cli_answer.py        # 答题助手 CLI
├── install.sh / install.bat  # 跨平台安装脚本
└── requirements.txt
```

---

## 🚀 安装与运行

### 前置要求
- Python 3.10+
- 智谱 API Key（[获取地址](https://open.bigmodel.cn)）
- Redis（可选，不装则自动降级内存模式）

### macOS / Linux 安装

```bash
# 1. 克隆项目
git clone https://github.com/anlisy/interview-copilot.git
cd interview-copilot

# 2. 一键安装（创建虚拟环境 + 装依赖 + 生成 .env 模板）
bash install.sh

# 3. 配置 API Key：编辑 .env，填入你的智谱 Key
#    ZHIPU_API_KEY=你的key

# 4.（可选）安装并启动 Redis
brew install redis
brew services start redis
```

### Windows 安装

```cmd
:: 1. 克隆项目
git clone https://github.com/anlisy/interview-copilot.git
cd interview-copilot

:: 2. 一键安装
install.bat

:: 3. 配置 API Key：编辑 .env 填入智谱 Key

:: 4. Redis 在 Windows 可选。不装用内存模式即可；
::    需完整功能可用 WSL 安装 Linux 版 Redis，或用 Memurai。
```

### 运行

**命令行版（推荐先试）：**
```bash
source venv/bin/activate      # Windows: venv\Scripts\activate
python cli.py                 # 模拟面试
python cli_predict.py         # 面试题预测
python cli_answer.py          # 答题助手
```

**Web 版：**
```bash
# 终端1：启动后端
uvicorn api:app --port 8000
# 终端2：启动前端
streamlit run app.py
```

> ⚠️ 若遇到 `SSL: CERTIFICATE_VERIFY_FAILED`，是本机代理软件（Clash 等）中间人解密所致。解决：关闭系统代理，或给 `open.bigmodel.cn` 添加代理直连规则。

---
## 📦 依赖说明

- **ChromaDB（向量库）**：纯 Python 库，随 pip install（安装脚本已含）装好，无需单独安装或启动服务。数据存本地 data/chroma_db/，首次导入时自动创建。零运维、开箱即用。

- **Redis（会话存储，可选）**：独立服务，需单独装启。装了支持多实例共享与持久化；不装自动降级内存模式，单机可用。
  - macOS：`brew install redis && brew services start redis`
  - Windows：可用 WSL 安装 Linux 版 Redis，或用 Memurai，或直接用内存模式。
  - 验证：`redis-cli ping` 返回 `PONG` 即正常。


## 📚 知识库：建立与 RAG 连接

系统的检索增强出题、命中率评估都依赖知识库。知识库按**约定式目录**组织——**文件夹名即分类**。

### 需要建立的四类知识库

```
data/knowledge/
├── 八股/     # Java/AI 八股题（出八股题时检索）
├── 面经/     # 真实被问过的面经（所有题型参考 + 命中率评估的 ground truth）
├── 实习/     # 实习经历细节（出实习追问题时检索）
└── 项目/     # 项目细节（出项目追问题时检索）
```

### 知识文件格式（markdown）

每个知识文件是一份 markdown，用标题作为"问题"、正文作为"答案"，一个"问题+答案"是一个知识单元。**注意不同分类的标题层级：**

- **八股**：用四级标题 `####`
- **面经**：用三级标题 `###`
- **实习/项目**：建议用二级标题 `##`

八股示例（`data/knowledge/八股/Java八股.md`）：
```markdown
#### HashMap扩容为什么是2倍
数组长度为2的次幂时，(数组长度-1)&哈希值能减少计算，与运算只需1个时钟周期...

#### ArrayList扩容为什么1.5倍
是内存使用与性能的权衡，扩容因子太大易造成内存浪费...
```

实习示例（`data/knowledge/实习/实习.md`）：
```markdown
## 双通道异步查询链路怎么设计的
最大难点是 Bitmap 丢失方差数据，我设计主线程秒返均值 + 异步 Spark 算 P 值...

## 查询幂等怎么保证的
提取核心语义参数用 MD5 生成全局 QueryID，任务提交前做幂等校验...
```

> 提示：飞书文档可直接"导出为 Markdown"。导出后确认标题层级，放入对应分类文件夹即可。

### 一键导入知识库（完成 RAG 连接）

把 md 放入对应文件夹后，运行导入命令，系统会自动：读取 md → 按标题切分成问答对 → 智谱 embedding 向量化 → 存入 ChromaDB。

```bash
python -m tools.import_knowledge
```

导入后会打印各分类条数，例如：
```
✅ 导入 198 条 [八股] 来自 Java八股.md
✅ 导入 129 条 [面经] 来自 面经.md
✅ 全部导入完成，共 327 条
```

### RAG 连接原理（自动，无需手动配置）

- **出题时**：系统按题型自动检索对应分类知识库（如 Java八股题查"八股"分类），把检索到的真实高频题拼进出题 prompt 增强生成。
- **命中率评估时**：把预测题与"面经"分类做语义相似度比对，算命中率。
- **答题助手**：检索所有分类，取最相关内容生成参考答案；检索不到则标注"AI 生成请核实"。

题型与知识库分类的映射定义在 `tools/question_tools.py` 的 `_TYPE_TO_CATEGORY`，如需调整可修改：
```python
_TYPE_TO_CATEGORY = {
    "Java八股": "八股",
    "AI应用八股": "八股",
    "实习追问": "实习",
    "项目追问": "项目",
    ...
}
```

### 更新知识库

- **新增知识**：把新 md 放入对应文件夹，重新运行 `python -m tools.import_knowledge`（新文件名追加，不覆盖）。
- **更新已有**：用同名文件覆盖原 md，重新导入即可覆盖。
- **新增分类**：直接新建文件夹（如 `data/knowledge/算法/`），在 `import_knowledge.py` 的 `CATEGORY_LEVEL` 补上层级，即可导入。

---

## 🔧 更换模型

系统采用**模型路由**——不同 Agent 用不同模型（出题用强模型、评分用快模型），平衡质量与成本。

### 在哪里改

模型配置在 `core/config.py` 的 `AGENT_MODEL_ROUTING`：

```python
AGENT_MODEL_ROUTING = {
    "interviewer": os.getenv("MODEL_INTERVIEWER", "glm-4-plus"),   # 出题：强模型
    "scorer":      os.getenv("MODEL_SCORER", "glm-4-flash"),        # 评分：快模型
    "reviewer":    os.getenv("MODEL_REVIEWER", "glm-4-air"),        # 复盘：中档
}
```

### 两种更改方式

**方式一：改代码（永久生效）**
直接修改上面字典的默认值，比如把出题模型换成 `glm-4.5-flash`：
```python
"interviewer": os.getenv("MODEL_INTERVIEWER", "glm-4.5-flash"),
```

**方式二：改环境变量（不改代码，推荐）**
在 `.env` 里覆盖，无需动代码：
```
MODEL_INTERVIEWER=glm-4.5-flash
MODEL_SCORER=glm-4-flash
MODEL_REVIEWER=glm-4-air
```

### 可选模型（智谱 GLM 系列）

| 模型 | 特点 | 建议用途 |
|------|------|---------|
| glm-4-plus | 最强，付费 | 出题（质量优先） |
| glm-4.5-flash | 强，免费 | 出题（省钱替代 plus） |
| glm-4-air | 中档 | 复盘 |
| glm-4-flash | 快，免费 | 评分、追问决策（速度优先） |

### 更换非智谱模型（如 OpenAI / 其他）

模型接入封装在 `core/llm.py` 的 `get_model()`，用的是 `OpenAIServerModel`（OpenAI 兼容协议）。若要换成其他厂商：
1. 在 `core/config.py` 改 `ZHIPU_API_BASE` 为目标厂商的 API 地址、`ZHIPU_API_KEY` 为对应 Key；
2. `AGENT_MODEL_ROUTING` 里的模型名改成目标厂商的模型 ID；
3. 只要目标厂商兼容 OpenAI 接口协议，无需改其他代码。

> embedding 模型在 `core/embedding.py` 的 `EMBED_MODEL`（默认 `embedding-3`），如需更换 embedding 在此修改。注意：更换 embedding 后，已入库的向量需重新导入（`python -m tools.import_knowledge`），且命中率阈值可能需重新标定。

### 验证模型是否生效

运行时后端会打印当前调用的模型，例如：
```
🤖 get_model: glm-4-plus      ← 出题
🤖 get_model: glm-4-flash     ← 评分
```
据此确认路由是否按预期生效。

---

## 🧪 测试

项目有 50+ 单元测试，全部通过 mock 隔离大模型，秒级运行、不消耗 API 额度：

```bash
pytest -q
```

---

## ⚙️ 配置说明（.env）

| 变量 | 必填 | 说明 |
|------|------|------|
| ZHIPU_API_KEY | 是 | 智谱 API Key |
| MODEL_INTERVIEWER | 否 | 出题模型，默认 glm-4-plus |
| MODEL_SCORER | 否 | 评分模型，默认 glm-4-flash |
| MODEL_REVIEWER | 否 | 复盘模型，默认 glm-4-air |

Redis 连接默认 `localhost:6379`，如需修改在 `agents/session_manager.py` 调整。

---


## 🗺️ 技术亮点

- 多 Agent 隔离架构 + Supervisor 状态机编排（评估隔离、防脱轨）
- Eval 驱动的预测命中率评估（面经做 ground truth，防数据泄漏）
- 检索增强出题 + 会话状态/行为分离持久化（Redis 可降级）
- Agent 动态追问 + 多层幻觉护栏（结构校验 + 内容约束）

---

## 📄 License

私有使用。