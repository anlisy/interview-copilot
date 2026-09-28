from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from pathlib import Path
from typing import Any


_SENSITIVE_KEYS = {"resume", "jd", "user_answer", "answer", "content", "api_key", "token", "authorization"}


def _safe_key(key: Any) -> str:
    return str(key).lower()


def summarize(value: Any, limit: int = 1200, _key: str | None = None) -> Any:
    if _key is not None and _safe_key(_key) in _SENSITIVE_KEYS:
        raw = str(value).encode("utf-8", errors="replace")
        return {"sha256": hashlib.sha256(raw).hexdigest(), "length": len(str(value))}
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, (list, tuple)):
        value = [summarize(x, limit=300) for x in value[:20]]
    elif isinstance(value, dict):
        value = {str(k): summarize(v, limit=300, _key=str(k)) for k, v in list(value.items())[:30]}
    else:
        value = str(value)
    raw = json.dumps(value, ensure_ascii=False, default=str) if not isinstance(value, str) else value
    if len(raw) <= limit:
        return value
    return raw[:limit] + "...<truncated>"


def safe_session_id(session_id: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", str(session_id)).strip("._")
    return value[:120] or "session"


class TraceRecorder:
    def __init__(self, root: str | Path = "storage/traces"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def record(self, event: dict[str, Any], session_id: str) -> str:
        trace_id = event.get("trace_id") or uuid.uuid4().hex
        safe_event = summarize(event, limit=12000)
        if not isinstance(safe_event, dict):
            safe_event = {"event_value": safe_event}
        payload = {
            "trace_id": trace_id,
            "ts": time.time(),
            "session_id": session_id,
            **safe_event,
        }
        path = self.root / f"{safe_session_id(session_id)}.jsonl"
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
        return trace_id
