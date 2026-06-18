import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# 项目根目录（跨平台用 Path）
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "interview.db"

# 模型配置
ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY")
ZHIPU_API_BASE = "https://open.bigmodel.cn/api/paas/v4/"
MODEL_ID = os.getenv("MODEL_ID", "glm-4-flash")

DATA_DIR.mkdir(exist_ok=True)
