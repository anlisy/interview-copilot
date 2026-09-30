from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Protocol

from .schema import SessionState


class SessionStateBackend(Protocol):
    def load(self, session_id: str) -> dict[str, Any] | None: ...
    def save(self, session_id: str, state: dict[str, Any]) -> None: ...
    def delete(self, session_id: str) -> None: ...


class FileSessionStateStore:
    """可序列化在线 Session 热状态；默认本地实现，便于测试与单机运行。"""

    def __init__(self, root: str | Path = ".agent_sessions"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _safe(self, session_id: str) -> str:
        return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in session_id)

    def _path(self, session_id: str) -> Path:
        return self.root / f"{self._safe(session_id)}.json"

    def load(self, session_id: str) -> dict[str, Any] | None:
        path = self._path(session_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def save(self, session_id: str, state: dict[str, Any]) -> None:
        path = self._path(session_id)
        fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent), text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2, default=str)
                f.flush()
                os.fsync(f.fileno())
            Path(tmp_name).replace(path)
        finally:
            tmp = Path(tmp_name)
            if tmp.exists():
                tmp.unlink()

    def delete(self, session_id: str) -> None:
        path = self._path(session_id)
        if path.exists():
            path.unlink()

    def load_state(self, session_id: str) -> SessionState:
        return SessionState.from_dict(self.load(session_id) or {"session_id": session_id})

    def save_state(self, state: SessionState) -> None:
        self.save(state.session_id, state.to_dict())


class Stage4RedisSessionBackend:
    """把 Stage4 RedisSessionStore 适配成 Stage8 的热状态后端。"""

    def __init__(self, redis_store: Any):
        self.redis = redis_store

    def load(self, session_id: str) -> dict[str, Any] | None:
        return self.redis.get(session_id)

    def save(self, session_id: str, state: dict[str, Any]) -> None:
        self.redis.set(session_id, state)

    def delete(self, session_id: str) -> None:
        self.redis.delete(session_id)

    def load_state(self, session_id: str) -> SessionState:
        return SessionState.from_dict(self.load(session_id) or {"session_id": session_id})

    def save_state(self, state: SessionState) -> None:
        self.save(state.session_id, state.to_dict())
