from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from .bm25 import BM25Index
from .models import MemoryRecord
from .raw_store import RawTrajectoryStore
from .rrf import reciprocal_rank_fusion
from .vector import VectorIndex


class MemoryStore:
    """ReMe-like 四步内核：capture -> index -> consolidate -> recall。"""

    def __init__(self, root: str | Path = ".agent_memory", vector_index: VectorIndex | None = None):
        self.root = Path(root)
        self.raw = RawTrajectoryStore(self.root / "raw")
        self.daily_dir = self.root / "daily"
        self.durable_dir = self.root / "durable"
        self.daily_dir.mkdir(parents=True, exist_ok=True)
        self.durable_dir.mkdir(parents=True, exist_ok=True)
        self.vector = vector_index
        self.bm25 = BM25Index()
        self._records: dict[str, MemoryRecord] = {}
        self._load_durable()

    def _load_durable(self) -> None:
        for path in sorted(self.durable_dir.glob("*.jsonl")):
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                record = MemoryRecord.from_dict(json.loads(line))
                self._records[record.record_id] = record
                self.bm25.add(record.record_id, record.content)
                if self.vector:
                    self.vector.add(record.record_id, record.content)

    def capture_turn(
        self,
        session_id: str,
        role: str,
        content: str,
        *,
        turn_id: str | None = None,
        stage: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryRecord:
        record = MemoryRecord(
            content=content,
            session_id=session_id,
            source="trajectory",
            memory_type="turn",
            turn_id=turn_id,
            stage=stage,
            metadata={"role": role, **(metadata or {})},
        )
        self.raw.append(record, role=role, content=content, extra=metadata)
        return record

    def capture_memory(self, record: MemoryRecord) -> MemoryRecord:
        self._records[record.record_id] = record
        self.bm25.add(record.record_id, record.content)
        if self.vector:
            self.vector.add(record.record_id, record.content)
        path = self.durable_dir / f"{record.session_id}.jsonl"
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record.to_dict(), ensure_ascii=False, default=str) + "\n")
        return record

    def capture_fact(
        self,
        session_id: str,
        content: str,
        *,
        turn_id: str | None = None,
        stage: str | None = None,
        confidence: float = 0.8,
        importance: float = 0.6,
        memory_type: str = "fact",
        metadata: dict[str, Any] | None = None,
    ) -> MemoryRecord:
        return self.capture_memory(
            MemoryRecord(
                content=content,
                session_id=session_id,
                source="interview",
                memory_type=memory_type,
                turn_id=turn_id,
                stage=stage,
                confidence=max(0.0, min(confidence, 1.0)),
                importance=max(0.0, min(importance, 1.0)),
                metadata=metadata or {},
            )
        )

    def consolidate(self, session_id: str) -> Path:
        rows = self.raw.read(session_id)
        path = self.daily_dir / f"{session_id}.jsonl"
        facts: list[dict[str, Any]] = []
        for row in rows:
            extra = row.get("extra") or {}
            if extra.get("memory_candidate") or extra.get("importance", 0) >= 0.7:
                facts.append(row)
        with path.open("w", encoding="utf-8") as f:
            for row in facts:
                f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
        return path

    def recall(self, query: str, limit: int = 5, session_id: str | None = None) -> list[dict[str, Any]]:
        bm25_hits = self.bm25.search(query, limit=max(limit * 3, 10))
        vector_hits = []
        if self.vector:
            vector_hits = [(h.doc_id, h.score) for h in self.vector.search(query, limit=max(limit * 3, 10))]

        if vector_hits:
            merged = reciprocal_rank_fusion([bm25_hits, vector_hits], limit=max(limit * 3, limit))
        else:
            merged = bm25_hits[: max(limit * 3, limit)]

        results = []
        for doc_id, fused_score in merged:
            record = self._records.get(doc_id)
            if not record:
                continue
            if session_id and record.session_id != session_id:
                continue
            results.append({
                "record_id": record.record_id,
                "content": record.content,
                "session_id": record.session_id,
                "memory_type": record.memory_type,
                "stage": record.stage,
                "timestamp": record.timestamp,
                "confidence": record.confidence,
                "importance": record.importance,
                "fused_score": round(fused_score, 6),
                "metadata": record.metadata,
            })
        return results[:limit]
