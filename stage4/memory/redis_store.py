from __future__ import annotations

import json
import os
from typing import Any


class RedisSessionStore:
    """Redis 只保存当前 Session 的热状态，不保存完整长期记忆。"""

    def __init__(self, client: Any, prefix: str = "interview:session:"):
        self.client = client
        self.prefix = prefix

    @classmethod
    def from_env(cls, url: str | None = None) -> "RedisSessionStore":
        import redis

        client = redis.Redis.from_url(url or os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True)
        client.ping()
        return cls(client)

    def _key(self, session_id: str) -> str:
        return f"{self.prefix}{session_id}"

    def set(self, session_id: str, state: dict[str, Any], ttl_seconds: int = 7200) -> None:
        self.client.set(self._key(session_id), json.dumps(state, ensure_ascii=False, default=str), ex=ttl_seconds)

    def get(self, session_id: str) -> dict[str, Any] | None:
        raw = self.client.get(self._key(session_id))
        return json.loads(raw) if raw else None

    def patch(self, session_id: str, values: dict[str, Any], ttl_seconds: int = 7200) -> dict[str, Any]:
        state = self.get(session_id) or {}
        state.update(values)
        self.set(session_id, state, ttl_seconds=ttl_seconds)
        return state

    def delete(self, session_id: str) -> None:
        self.client.delete(self._key(session_id))
