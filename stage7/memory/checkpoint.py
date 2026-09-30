from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import tempfile


class CheckpointStore:
    """文件级阶段 checkpoint；用于幂等恢复，而不是替代 Session 状态。"""

    def __init__(self, root: str | Path = ".agent_memory/checkpoints"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, job_id: str) -> Path:
        safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in job_id)
        return self.root / f"{safe}.json"

    def load(self, job_id: str) -> dict[str, Any] | None:
        path = self._path(job_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def save(self, job_id: str, state: dict[str, Any]) -> None:
        path = self._path(job_id)
        payload = dict(state)
        payload["job_id"] = job_id
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent), text=True)
        try:
            with open(fd, "w", encoding="utf-8", closefd=True) as f:
                json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
                f.flush()
            Path(tmp_name).replace(path)
        finally:
            tmp = Path(tmp_name)
            if tmp.exists():
                tmp.unlink()

    def clear(self, job_id: str) -> None:
        path = self._path(job_id)
        if path.exists():
            path.unlink()
