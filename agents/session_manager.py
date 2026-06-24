"""Supervisor 会话管理：一场面试 = 一个 session_id = 一个常驻 Supervisor 实例。
L2-a 用内存字典（单进程）；L2-b 换 Redis（多进程共享 + TTL）。
"""
import uuid
from agents.supervisor import Supervisor


class SessionManager:
    def __init__(self):
        self._sessions: dict[str, Supervisor] = {}

    def create(self) -> str:
        sid = uuid.uuid4().hex[:12]
        self._sessions[sid] = Supervisor()
        return sid

    def get(self, sid: str) -> Supervisor:
        sup = self._sessions.get(sid)
        if sup is None:
            raise KeyError(f"会话不存在或已过期: {sid}")
        return sup

    def drop(self, sid: str):
        self._sessions.pop(sid, None)


session_manager = SessionManager()
