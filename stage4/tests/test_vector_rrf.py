from stage4.memory.memory_store import MemoryStore
from stage4.memory.vector import InMemoryVectorIndex, VectorHit


class FakeEmbedding:
    def embed(self, texts):
        rows = []
        for text in texts:
            t = text.lower()
            rows.append([
                1.0 if "redis" in t else 0.0,
                1.0 if "击穿" in t else 0.0,
                1.0 if "互斥锁" in t else 0.0,
            ])
        return rows


def test_vector_search_works():
    index = InMemoryVectorIndex(FakeEmbedding())
    index.add("a", "Redis 缓存击穿使用互斥锁")
    index.add("b", "Kafka 消息消费")
    hits = index.search("Redis 击穿", limit=2)
    assert isinstance(hits[0], VectorHit)
    assert hits[0].doc_id == "a"


def test_memory_store_can_fuse_bm25_and_vector(tmp_path):
    vector = InMemoryVectorIndex(FakeEmbedding())
    store = MemoryStore(tmp_path / "mem", vector_index=vector)
    store.capture_fact("s1", "Redis 缓存击穿使用互斥锁", importance=0.9)
    store.capture_fact("s1", "Kafka 异步消费", importance=0.7)
    hits = store.recall("Redis 击穿", limit=2)
    assert hits
    assert hits[0]["content"] == "Redis 缓存击穿使用互斥锁"
    assert hits[0]["fused_score"] > 0
