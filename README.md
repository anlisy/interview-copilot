# 🎯 Interview Copilot —— AI 模拟面试系统

基于多 Agent 架构的 AI 模拟面试助手。输入简历和 JD，AI 面试官会诊断简历、出题、动态追问、评分、复盘，并用真实面经评估预测命中率。

## ✨ 核心特性

- **🤖 多 Agent 架构**：面试官/评分/复盘三个独立 Agent，上下文隔离、评估隔离（出题者不接触评分逻辑）
- **🔀 状态机调度**：Supervisor 状态机严格编排面试流程，防止 Agent 脱轨
- **🔁 动态追问**：面试官读懂回答深度，答浅了自动追问，5 层递进（事实→技术→数据→边界）
- **📚 知识库 RAG**：真实面经 + 八股题库向量化检索，出题基于真实高频题
- **📊 预测命中率评估**：用真实面经做 ground truth，量化"模拟真实面试"的准确度
- **🔍 简历诊断**：面试官视角分析简历亮点、风险、预判追问方向
- **🎚️ 模型路由**：不同 Agent 用不同模型（出题用强模型、评分用快模型），平衡质量与成本
- **💾 Redis 持久化**：会话状态存 Redis（不装则降级内存），支持多实例部署
- **🛡️ 多层护栏**：题型枚举校验 + 内容一致性约束 + 三层追问兜底，约束大模型幻觉

## 🏗️ 架构

前端(Streamlit) / CLI ──> Supervisor(状态机调度) ├─ InterviewerAgent 出题+追问+诊断 ├─ ScorerAgent 评分 └─ ReviewerAgent 复盘 ├─ 知识库 RAG (chromadb + 智谱embedding) ├─ Redis 会话持久化 └─ Eval 命中率评估

## 🚀 快速开始

### 一键安装

Mac / Linux：
bash install.sh
Windows：
install.bat
### 配置 API Key

编辑 .env，填入智谱 API Key（https://open.bigmodel.cn）：
ZHIPU_API_KEY=你的key

shell

### 使用

命令行版（推荐先试）：
source venv/bin/activate python cli.py

Windows 激活虚拟环境用：venv\Scripts\activate

Web 版：
uvicorn api:app --port 8000 # 终端1 后端 streamlit run app.py # 终端2 前端

shell

## 📚 知识库（可选，增强出题）

把面经/八股整理成 markdown，按分类放入对应文件夹，一键导入：

data/knowledge/ ├── 八股/ Java/AI 八股题 ├── 面经/ 真实面经 ├── 实习/ 实习经历细节 └── 项目/ 项目细节


导入：
python -m tools.import_knowledge

markdown

约定：文件夹名 = 知识分类。加新分类只需新建文件夹放 md。

## 🔧 技术栈

- 后端：FastAPI + Supervisor 状态机
- 前端：Streamlit
- Agent：smolagents + 智谱 GLM
- 向量库：chromadb + 智谱 embedding-3
- 会话存储：Redis（可降级内存）
- 测试：pytest（46 个用例，mock LLM 秒级运行）

## 🧪 测试

pytest -q

csharp

## 📖 依赖说明

- chromadb：纯 Python 库，pip 安装即用，数据存本地文件，无需单独启动服务
- Redis：可选。装了支持多进程/持久化；不装自动降级内存模式（单机可用）
  - Mac: brew install redis 然后 brew services start redis
  - Windows: 可用 WSL 或 Memurai，或直接用内存模式

## 📄 License

私有使用。
