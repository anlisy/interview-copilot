from smolagents import OpenAIServerModel
from core.config import ZHIPU_API_KEY, ZHIPU_API_BASE, MODEL_ID


def get_model(model_id: str = None):
    """获取 smolagents 模型实例（接智谱 GLM）"""
    return OpenAIServerModel(
        model_id=model_id or MODEL_ID,
        api_base=ZHIPU_API_BASE,
        api_key=ZHIPU_API_KEY,
    )
