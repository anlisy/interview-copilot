@echo off
chcp 65001 >nul
echo ========================================
echo   Interview Copilot 安装 (Windows)
echo ========================================

if not exist venv (
    python -m venv venv
    echo [OK] 创建虚拟环境
)
call venv\Scripts\activate.bat

echo [..] 安装依赖...
pip install -q -r requirements.txt
echo [OK] 依赖安装完成

if not exist .env (
    echo ZHIPU_API_KEY=在这里填你的智谱API_Key> .env
    echo [!] 已创建 .env，请编辑填入智谱 API Key
)

echo.
echo ========================================
echo [OK] 安装完成！使用方式:
echo   命令行版:  venv\Scripts\activate 然后 python cli.py
echo   Web版:     venv\Scripts\activate
echo              窗口1: uvicorn api:app --port 8000
echo              窗口2: streamlit run app.py
echo.
echo   首次用知识库: python -m tools.import_knowledge
echo.
echo [i] Redis 在 Windows 可选。不装会用内存模式（推荐）。
echo     需完整功能可用 WSL 或 Memurai。
echo ========================================
