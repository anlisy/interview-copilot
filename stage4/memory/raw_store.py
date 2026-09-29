from __future__ import annotations

from pathlib import Path
import json
from typing import Any, Iterable

from .models import MemoryRecord


class RawTrajectoryStore:
    """原始轨迹：JSONL 作为事实源，Markdown 只是可读导出。"""

    def __init__(self, root: str | Path = ".agent_memory/raw"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _jsonl_path(self, session_id: str) -> Path:
        return self.root / f"{session_id}.jsonl"

    def _markdown_path(self, session_id: str) -> Path:
        return self.root / f"{session_id}.md"

    def append(self, record: MemoryRecord, role: str, content: str, extra: dict[str, Any] | None = None) -> None:
        payload = {
            "record": record.to_dict(),
            "role": role,
            "content": content,
            "extra": extra or {},
        }
        with self._jsonl_path(record.session_id).open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")

        with self._markdown_path(record.session_id).open("a", encoding="utf-8") as f:
            f.write(f"\n## {record.timestamp} | {role}\n\n{content.strip()}\n")

    def read(self, session_id: str, limit: int | None = None) -> list[dict[str, Any]]:
        path = self._jsonl_path(session_id)
        if not path.exists():
            return []
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        return rows[-limit:] if limit else rows
