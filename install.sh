#!/bin/bash
# Interview Copilot 一键安装 (Mac/Linux)
set -e
echo "========================================"
echo "  Interview Copilot 安装 (Mac/Linux)"
echo "========================================"

# 1. 虚拟环境
if [ ! -d venv ]; then
    python3 -m venv venv
    echo "✅ 创建虚拟环境"
fi
source venv/bin/activate

# 2. 依赖
echo "⏳ 安装依赖..."
pip install -q -r requirements.txt
echo "✅ 依赖安装完成"

# 3. .env
if [ ! -f .env ]; then
    echo "ZHIPU_API_KEY=在这里填你的智谱API_Key" > .env
    echo "⚠️  已创建 .env，请编辑填入智谱 API Key（https://open.bigmodel.cn）"
fi

# 4. Redis（可选）
if command -v redis-cli &> /dev/null && redis-cli ping &> /dev/null; then
    echo "✅ Redis 已就绪"
else
    echo "ℹ️  未运行 Redis（可选，不装会用内存模式）"
    echo "   安装: brew install redis && brew services start redis"
fi

echo ""
echo "========================================"
echo "✅ 安装完成！使用方式："
echo "  命令行版:  source venv/bin/activate && python cli.py"
echo "  Web版:     source venv/bin/activate"
echo "             终端1: uvicorn api:app --port 8000"
echo "             终端2: streamlit run app.py"
echo ""
echo "  首次用知识库: python -m tools.import_knowledge"
echo "========================================"
