# Interview Copilot

基于 smolagents 的自进化面试陪练 Agent（技术岗模拟面试 + 打分 + 复盘）。

## 技术栈
- Python 3.10+
- smolagents（Agent 内核，非 LangChain）
- 智谱 GLM API（OpenAI 兼容）
- streamlit（界面）
- SQLite（记录存储）

## 安装
\`\`\`bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # 填入你的智谱 API key
\`\`\`

## 验证环境
\`\`\`bash
python test_run.py              # 输出 579 即接通成功
\`\`\`

## 运行
\`\`\`bash
streamlit run app.py
\`\`\`

## 开发路线
- L1: 简历+JD → 出题 → 答题 → 打分 → 复盘 → 记录保存查看（当前）
- L2: 多 Agent + 题库 + 语音输入 + Run Trace
- L3: 面经对比 + Eval 自进化闭环
