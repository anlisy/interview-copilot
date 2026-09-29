from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Protocol, Sequence


class EmbeddingProvider(Protocol):
    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


@dataclass
class VectorHit:
    doc_id: str
    score: float


class VectorIndex:
    """可替换的向量索引。核心层不绑定具体向量数据库。"""

    def add(self, doc_id: str, text: str) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def search(self, query: str, limit: int = 10) -> list[VectorHit]:  # pragma: no cover - interface
        raise NotImplementedError


class InMemoryVectorIndex(VectorIndex):
    """内存向量索引，适合测试和小规模本地调试。"""

    def __init__(self, provider: EmbeddingProvider):
        self.provider = provider
        self._vectors: dict[str, list[float]] = {}
        self._texts: dict[str, str] = {}

    def add(self, doc_id: str, text: str) -> None:
        self._vectors[doc_id] = self.provider.embed([text])[0]
        self._texts[doc_id] = text

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(y * y for y in b))
        return dot / (na * nb) if na and nb else 0.0

    def search(self, query: str, limit: int = 10) -> list[VectorHit]:
        qv = self.provider.embed([query])[0]
        hits = [VectorHit(doc_id, self._cosine(qv, vec)) for doc_id, vec in self._vectors.items()]
        hits.sort(key=lambda hit: (-hit.score, hit.doc_id))
        return [h for h in hits[:limit] if h.score > 0]


class HashEmbeddingProvider:
    """无外部依赖的可重复测试用 embedding，不用于生产语义检索。"""

    def __init__(self, dimensions: int = 128):
        self.dimensions = dimensions

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            vector = [0.0] * self.dimensions
            for token in (text or "").lower().split():
                vector[hash(token) % self.dimensions] += 1.0
            vectors.append(vector)
        return vectors


class ChromaVectorIndex(VectorIndex):
    """可选 Chroma 持久化适配器；不在核心层强制安装 chromadb。"""

    def __init__(self, path: str, collection: str, provider: EmbeddingProvider):
        import chromadb

        self.provider = provider
        client = chromadb.PersistentClient(path=path)
        self.collection = client.get_or_create_collection(
            name=collection,
            metadata={"hnsw:space": "cosine"},
        )

    def add(self, doc_id: str, text: str) -> None:
        vector = self.provider.embed([text])[0]
        self.collection.upsert(ids=[doc_id], documents=[text], embeddings=[vector])

    def search(self, query: str, limit: int = 10) -> list[VectorHit]:
        result = self.collection.query(
            query_embeddings=self.provider.embed([query]),
            n_results=limit,
        )
        ids = result.get("ids", [[]])[0]
        distances = result.get("distances", [[]])[0]
        hits = []
        for doc_id, distance in zip(ids, distances):
            hits.append(VectorHit(str(doc_id), max(0.0, 1.0 - float(distance))))
        return hits


class HTTPEmbeddingProvider:
    """通用 OpenAI-compatible embedding HTTP 适配器；endpoint/model 由环境决定。"""

    def __init__(self, endpoint: str, api_key: str, model: str, timeout: float = 15.0):
        self.endpoint = endpoint
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        import requests

        resp = requests.post(
            self.endpoint,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={"model": self.model, "input": list(texts)},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        payload = resp.json()
        data = sorted(payload["data"], key=lambda row: row.get("index", 0))
        return [row["embedding"] for row in data]
