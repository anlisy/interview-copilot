"""会话管理：会话状态存 Redis，Supervisor 临时重建。

设计：
- SessionStore 抽象接口，RedisStore / MemoryStore 两个实现。
- Redis 不可用时自动降级到内存（容错）。
- 会话状态带 TTL 自动过期，防止内存/Redis 泄漏。
- Supervisor 只持久化 state 字段；Agent 无状态，每次重建。
"""
import json
import uuid
from abc import ABC, abstractmethod

from agents.supervisor import Supervisor

SESSION_TTL = 3600          # 会话 1 小时无操作自动过期
REDIS_KEY_PREFIX = "interview:session:"


# ---------- 存储抽象 ----------
class SessionStore(ABC):
    @abstractmethod
    def save(self, sid: str, data: dict) -> None: ...

    @abstractmethod
    def load(self, sid: str) -> dict | None: ...

    @abstractmethod
    def delete(self, sid: str) -> None: ...


class RedisStore(SessionStore):
    """Redis 实现：状态存为 JSON 字符串，带 TTL。"""
    def __init__(self, client):
        self._r = client

    def _key(self, sid: str) -> str:
        return f"{REDIS_KEY_PREFIX}{sid}"

    def save(self, sid: str, data: dict) -> None:
        # 每次写入都刷新 TTL（滑动过期）
        self._r.set(self._key(sid), json.dumps(data), ex=SESSION_TTL)

    def load(self, sid: str) -> dict | None:
        raw = self._r.get(self._key(sid))
        if raw is None:
            return None
        # 读到也刷新 TTL（保持活跃会话不过期）
        self._r.expire(self._key(sid), SESSION_TTL)
        return json.loads(raw)

    def delete(self, sid: str) -> None:
        self._r.delete(self._key(sid))


class MemoryStore(SessionStore):
    """内存实现：降级用 / 测试用（无 TTL，进程级）。"""
    def __init__(self):
        self._data: dict[str, dict] = {}

    def save(self, sid: str, data: dict) -> None:
        self._data[sid] = data

    def load(self, sid: str) -> dict | None:
        return self._data.get(sid)

    def delete(self, sid: str) -> None:
        self._data.pop(sid, None)


# ---------- 选择存储后端（Redis 优先，失败降级内存）----------
def _build_store() -> SessionStore:
    try:
        import redis
        client = redis.Redis(host="localhost", port=6379,
                             decode_responses=True, socket_connect_timeout=2)
        client.ping()   # 探活
        print("✅ SessionManager 使用 Redis 存储")
        return RedisStore(client)
    except Exception as e:
        print(f"⚠️ Redis 不可用({e})，降级到内存存储")
        return MemoryStore()


# ---------- 会话管理器 ----------
class SessionManager:
    def __init__(self, store: SessionStore = None):
        self._store = store or _build_store()

    def create(self) -> str:
        """新建会话，返回 session_id。"""
        sid = uuid.uuid4().hex[:12]
        sup = Supervisor()
        self._store.save(sid, {"state": sup.dump_state()})
        return sid

    def get(self, sid: str) -> Supervisor:
        """从存储读状态，临时重建 Supervisor。"""
        data = self._store.load(sid)
        if data is None:
            raise KeyError(f"会话不存在或已过期: {sid}")
        return Supervisor.from_state(data["state"])

    def save(self, sid: str, sup: Supervisor) -> None:
        """把 Supervisor 的最新状态写回存储（业务跑完必须调用）。"""
        # 写回前确认会话还在（防止对已过期会话写入）
        if self._store.load(sid) is None:
            raise KeyError(f"会话不存在或已过期: {sid}")
        self._store.save(sid, {"state": sup.dump_state()})

    def drop(self, sid: str) -> None:
        self._store.delete(sid)


# 全局单例
session_manager = SessionManager()
