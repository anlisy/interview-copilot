"""智谱 embedding 封装：把文本转向量，供 chromadb 使用。
智谱 embedding API 单次最多 64 条，超过要分批。
"""
from openai import OpenAI
from core.config import ZHIPU_API_KEY, ZHIPU_API_BASE

_client = OpenAI(api_key=ZHIPU_API_KEY, base_url=ZHIPU_API_BASE)
EMBED_MODEL = "embedding-3"
BATCH_SIZE = 64   # 智谱单次上限


def embed_texts(texts):
    """批量转向量，自动分批（每批 <=64 条）。"""
    all_embeddings = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i:i + BATCH_SIZE]
        resp = _client.embeddings.create(model=EMBED_MODEL, input=batch)
        all_embeddings.extend(d.embedding for d in resp.data)
        print(f"  🔢 已向量化 {min(i + BATCH_SIZE, len(texts))}/{len(texts)}")
    return all_embeddings


def embed_one(text):
    return embed_texts([text])[0]
