from functools import lru_cache
from smolagents import OpenAIServerModel
from core.config import ZHIPU_API_KEY, ZHIPU_API_BASE, MODEL_ID


@lru_cache(maxsize=4)
def get_model(model_id: str = None):
    """获取 smolagents 模型实例（接智谱 GLM）"""
    return OpenAIServerModel(
        model_id=model_id or MODEL_ID,
        api_base=ZHIPU_API_BASE,
        api_key=ZHIPU_API_KEY,
        max_tokens=2000,
        temperature=0.7,
        timeout=60,          # 单次请求最多等 60 秒，进 kwargs 透传
    )


import time
from openai import RateLimitError
from smolagents import ChatMessage, MessageRole


def generate_with_retry(prompt: str, max_retry: int = 3, model_id: str = None) -> str:
    """统一单轮调用：传 prompt 返回纯文本。429 自动等待重试，最多 max_retry 次。"""
    model = get_model(model_id)
    messages = [ChatMessage(role=MessageRole.USER, content=prompt)]
    for attempt in range(max_retry):
        try:
            return model.generate(messages).content
        except RateLimitError:
            if attempt < max_retry - 1:
                wait = (attempt + 1) * 5
                print(f"  ⏳ 限流，等待 {wait}s 后重试 ({attempt+1}/{max_retry})...")
                time.sleep(wait)
            else:
                raise RuntimeError("智谱限流多次，请稍后再试或降低请求频率")
