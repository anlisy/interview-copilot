"""知识库工具：解析 markdown → 切分成问答块 → 智谱向量化 → 存 chromadb。"""
import re
import chromadb
from pathlib import Path
from core.config import ROOT
from core.embedding import embed_texts, embed_one

CHROMA_DIR = ROOT / "data" / "chroma_db"
COLLECTION_NAME = "knowledge"


def _get_collection():
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def _clean(text: str) -> str:
    text = re.sub(r"!\[Image\]\([^)]*\)", "", text)
    text = text.replace("\\", "")
    return text.strip()


def parse_markdown(md_path: Path, q_level: int = 4) -> list:
    """按指定层级标题切分成问答块。q_level: 问题用几级标题(八股4=####，面经3=###)。"""
    q_prefix = "#" * q_level + " "
    topic_prefix = "#" * (q_level - 1) + " "
    lines = md_path.read_text(encoding="utf-8").split("\n")
    blocks = []
    cur_topic = ""
    cur_q = None
    cur_body = []

    def flush():
        if cur_q:
            answer = _clean("\n".join(cur_body))
            if answer:
                blocks.append({
                    "question": _clean(cur_q),
                    "answer": answer,
                    "topic": _clean(cur_topic),
                })

    for line in lines:
        if line.startswith(q_prefix):
            flush()
            cur_q = line[len(q_prefix):].strip()
            cur_body = []
        elif topic_prefix != "# " and line.startswith(topic_prefix):
            flush()
            cur_topic = line[len(topic_prefix):].strip()
            cur_q = None
            cur_body = []
        elif line.startswith("# ") and not line.startswith("## "):
            continue
        else:
            if cur_q:
                cur_body.append(line)
    flush()
    return blocks


def import_markdown(md_path: Path, category: str, q_level: int = 4):
    blocks = parse_markdown(md_path, q_level=q_level)
    if not blocks:
        print(f"⚠️ {md_path.name} 没解析出内容")
        return 0
    col = _get_collection()
    source = md_path.stem
    docs = [f"{b['question']}\n{b['answer']}" for b in blocks]
    embeddings = embed_texts(docs)
    ids = [f"{category}_{source}_{i}" for i in range(len(blocks))]
    metadatas = [
        {"category": category, "source": source,
         "topic": b["topic"], "question": b["question"]}
        for b in blocks
    ]
    col.upsert(ids=ids, embeddings=embeddings, documents=docs, metadatas=metadatas)
    print(f"✅ 导入 {len(blocks)} 条 [{category}] 来自 {md_path.name}")
    return len(blocks)


def search_knowledge(query: str, category: str = None, top_k: int = 3) -> list:
    """检索知识。返回含相似度分数。
    similarity = 1 - cosine_distance，范围[0,1]，越大越相似。"""
    col = _get_collection()
    query_emb = embed_one(query)
    where = {"category": category} if category else None
    res = col.query(query_embeddings=[query_emb], n_results=top_k, where=where)
    docs = res.get("documents", [[]])[0]
    metas = res.get("metadatas", [[]])[0]
    dists = res.get("distances", [[]])[0]
    out = []
    for i, (d, m) in enumerate(zip(docs, metas)):
        dist = dists[i] if i < len(dists) else 1.0
        out.append({"document": d, "metadata": m, "similarity": round(1 - dist, 4)})
    return out
