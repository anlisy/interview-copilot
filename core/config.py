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

# ---------- L2-c: Agent 模型路由 ----------
# 每个 Agent 按任务性质匹配不同模型，平衡质量与成本。
# 出题要质量→强模型；评分机械→快模型；复盘中等→中档模型。
AGENT_MODEL_ROUTING = {
    "interviewer": os.getenv("MODEL_INTERVIEWER", "glm-4-plus"),   # 出题：旗舰
    "scorer":      os.getenv("MODEL_SCORER", "glm-4-flash"),        # 评分：快
    "reviewer":    os.getenv("MODEL_REVIEWER", "glm-4-air"),        # 复盘：中档
}

def get_model_for_agent(agent_name: str) -> str:
    """按 Agent 名返回其应使用的模型 ID，未配置则回退默认 MODEL_ID。"""
    return AGENT_MODEL_ROUTING.get(agent_name, MODEL_ID)
