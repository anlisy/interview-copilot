from __future__ import annotations
import json
from pathlib import Path
from typing import Iterable


def load_jsonl(path: str | Path) -> list[dict]:
    rows = []
    for lineno, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSONL at {path}:{lineno}") from exc
    return rows


def validate_cases(rows: Iterable[dict], *, prediction: bool = False) -> None:
    required = {"id", "ranked_ids"} if prediction else {
        "id", "canonical_question", "question_intent", "relevant_ids",
        "graded_relevance", "required_concepts", "required_topics",
        "disallowed_claims", "expected_tool", "expected_memory_ids",
    }
    for row in rows:
        missing = required - set(row)
        if missing:
            raise ValueError(f"case {row.get('id')} missing fields: {sorted(missing)}")
