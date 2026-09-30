from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from uuid import uuid4


class OnlineTraceRecorder:
    """只记录在线闭环的可观测摘要，不把整份简历/JD/原始答案写入 trace。"""

    def __init__(self, root: str | Path = "storage/traces/stage8"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _hash(value: str) -> str:
        return hashlib.sha256((value or "").encode("utf-8")).hexdigest()

    def new_trace_id(self) -> str:
        return uuid4().hex

    def append(self, event: dict[str, Any]) -> None:
        event = dict(event)
        session_id = str(event.get("session_id", "unknown"))
        safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in session_id)
        path = self.root / f"{safe}.jsonl"
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")

    def record_turn(self, *, trace_id: str, session_id: str, task: str, result: dict[str, Any]) -> None:
        self.append({
            "trace_id": trace_id,
            "session_id": session_id,
            "event": "online_turn",
            "task_hash": self._hash(task),
            "task_len": len(task),
            "skill": result.get("skill"),
            "tool": result.get("tool"),
            "intent": result.get("intent"),
            "agent_engine": result.get("agent_output", {}).get("engine"),
            "agent_latency_ms": result.get("agent_output", {}).get("latency_ms", 0),
            "agent_total_tokens": result.get("agent_output", {}).get("total_tokens", 0),
            "agent_cost": result.get("agent_output", {}).get("cost", 0),
        })
