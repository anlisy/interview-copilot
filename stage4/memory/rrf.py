from __future__ import annotations


def reciprocal_rank_fusion(
    rankings: list[list[tuple[str, float]]],
    k: int = 60,
    limit: int = 10,
) -> list[tuple[str, float]]:
    """把 BM25 / vector 等多个排序列表融合成一个稳定排名。"""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, (doc_id, _score) in enumerate(ranking, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    merged = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    return merged[:limit]
