from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
import json
import os

from .schema import MemoryCandidate, MemoryEvidence


class MemoryExtractor(ABC):
    """将原始 Session 轨迹提炼为候选长期记忆。"""

    @abstractmethod
    def extract(self, session_id: str, rows: list[dict[str, Any]]) -> list[MemoryCandidate]:
        raise NotImplementedError


def _row_evidence(row: dict[str, Any], index: int) -> MemoryEvidence:
    record = row.get("record") or {}
    source_id = str(record.get("record_id") or row.get("id") or f"row-{index}")
    return MemoryEvidence(
        source_id=source_id,
        role=str(row.get("role") or (record.get("metadata") or {}).get("role") or "unknown"),
        content=str(row.get("content") or "").strip(),
        stage=record.get("stage"),
        timestamp=record.get("timestamp"),
    )


class RuleMemoryExtractor(MemoryExtractor):
    """保守规则抽取：只提炼轨迹中明确标记为 candidate 的内容。"""

    def extract(self, session_id: str, rows: list[dict[str, Any]]) -> list[MemoryCandidate]:
        out: list[MemoryCandidate] = []
        for i, row in enumerate(rows):
            extra = row.get("extra") or {}
            record = row.get("record") or {}
            content = str(row.get("content") or "").strip()
            if not content:
                continue
            marked = bool(extra.get("memory_candidate"))
            important = float(extra.get("importance", 0) or 0) >= 0.7
            if not (marked or important):
                continue
            evidence = [_row_evidence(row, i)]
            out.append(
                MemoryCandidate(
                    content=content,
                    memory_type=str(extra.get("memory_type") or "fact"),
                    confidence=float(extra.get("confidence", record.get("confidence", 0.8)) or 0.8),
                    importance=float(extra.get("importance", record.get("importance", 0.6)) or 0.6),
                    evidence=evidence,
                    source_session_id=session_id,
                    metadata={
                        "extractor": "rule",
                        "source_stage": record.get("stage"),
                        "source_role": row.get("role"),
                    },
                )
            )
        return _dedup_candidates(out)


class ZhipuMemoryExtractor(MemoryExtractor):
    """直接调用智谱兼容 OpenAI API 做候选记忆抽取。"""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ):
        self.api_key = api_key or os.getenv("ZHIPU_API_KEY")
        self.model = model or os.getenv("ZHIPU_MODEL", "glm-4-flash")
        self.base_url = base_url or os.getenv("ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
        if not self.api_key:
            raise ValueError("ZHIPU_API_KEY is required for glm extraction")

    def _client(self):
        from openai import OpenAI
        return OpenAI(api_key=self.api_key, base_url=self.base_url)

    def _prompt(self, session_id: str, rows: list[dict[str, Any]]) -> str:
        compact = []
        for i, row in enumerate(rows):
            record = row.get("record") or {}
            compact.append({
                "index": i,
                "record_id": record.get("record_id"),
                "role": row.get("role"),
                "stage": record.get("stage"),
                "timestamp": record.get("timestamp"),
                "content": row.get("content", ""),
                "extra": row.get("extra") or {},
            })
        return f"""You are a conservative long-term memory extractor for a technical interview system.
Extract only reusable facts that are directly supported by the provided trajectory.
Do not infer personality, mental state, private traits, or facts not explicitly evidenced.
Do not copy an entire conversation. Prefer concise facts that can improve a future interview.
Possible memory_type values: fact, skill_strength, weakness, preference, verified_experience, interview_performance.
Each candidate must cite one or more evidence indexes from the input.
Confidence measures evidence strength, not how certain the model sounds.
Return ONLY a JSON array. No markdown fences.

Required object shape:
{{
  "content": "concise reusable fact",
  "memory_type": "fact",
  "confidence": 0.0,
  "importance": 0.0,
  "evidence_indexes": [0, 2]
}}

session_id={session_id}
trajectory={json.dumps(compact, ensure_ascii=False)}
"""

    def extract(self, session_id: str, rows: list[dict[str, Any]]) -> list[MemoryCandidate]:
        if not rows:
            return []
        response = self._client().chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": self._prompt(session_id, rows)}],
            temperature=0,
        )
        text = response.choices[0].message.content or "[]"
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text
            if text.endswith("```"):
                text = text[:-3]
        payload = json.loads(text)
        if not isinstance(payload, list):
            raise ValueError("GLM memory extraction must return a JSON array")

        out: list[MemoryCandidate] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            content = str(item.get("content") or "").strip()
            if not content:
                continue
            evidence = []
            for idx in item.get("evidence_indexes", []):
                if isinstance(idx, int) and 0 <= idx < len(rows):
                    evidence.append(_row_evidence(rows[idx], idx))
            if not evidence:
                continue
            out.append(MemoryCandidate(
                content=content,
                memory_type=str(item.get("memory_type") or "fact"),
                confidence=float(item.get("confidence", 0.5)),
                importance=float(item.get("importance", 0.5)),
                evidence=evidence,
                source_session_id=session_id,
                metadata={"extractor": "glm", "model": self.model},
            ))
        return _dedup_candidates(out)


def _dedup_candidates(items: list[MemoryCandidate]) -> list[MemoryCandidate]:
    seen: set[str] = set()
    out: list[MemoryCandidate] = []
    for item in items:
        key = f"{item.memory_type}:{item.content_hash}"
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out
