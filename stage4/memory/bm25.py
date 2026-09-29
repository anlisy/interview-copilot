from __future__ import annotations

from collections import Counter
import math
import re
from typing import Iterable


_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]")


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall((text or "").lower())


class BM25Index:
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self._docs: dict[str, str] = {}
        self._tokens: dict[str, list[str]] = {}

    def add(self, doc_id: str, text: str) -> None:
        self._docs[doc_id] = text
        self._tokens[doc_id] = tokenize(text)

    def remove(self, doc_id: str) -> None:
        self._docs.pop(doc_id, None)
        self._tokens.pop(doc_id, None)

    def clear(self) -> None:
        self._docs.clear()
        self._tokens.clear()

    def search(self, query: str, limit: int = 10) -> list[tuple[str, float]]:
        q = tokenize(query)
        if not q or not self._docs:
            return []
        n = len(self._docs)
        avgdl = sum(len(v) for v in self._tokens.values()) / max(n, 1)
        df = Counter()
        for tokens in self._tokens.values():
            for token in set(tokens):
                df[token] += 1
        scored: list[tuple[str, float]] = []
        for doc_id, tokens in self._tokens.items():
            tf = Counter(tokens)
            dl = len(tokens) or 1
            score = 0.0
            for term in q:
                freq = tf.get(term, 0)
                if not freq:
                    continue
                idf = math.log(1.0 + (n - df[term] + 0.5) / (df[term] + 0.5))
                denom = freq + self.k1 * (1 - self.b + self.b * dl / max(avgdl, 1e-9))
                score += idf * freq * (self.k1 + 1) / denom
            if score > 0:
                scored.append((doc_id, score))
        scored.sort(key=lambda item: (-item[1], item[0]))
        return scored[:limit]
