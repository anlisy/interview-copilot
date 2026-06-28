"""SessionManager 测试：用 MemoryStore 注入，不依赖真实 Redis"""
import pytest
from agents.session_manager import SessionManager, MemoryStore
from core.state import InterviewState


@pytest.fixture
def sm():
    """每个测试用独立的内存存储，互不干扰。"""
    return SessionManager(store=MemoryStore())


def test_create_and_get(sm):
    """创建会话后能读出，初始状态是 INIT"""
    sid = sm.create()
    sup = sm.get(sid)
    assert sup.state == InterviewState.INIT


def test_state_persisted_after_save(sm):
    """save 后状态被持久化，重新 get 能读到新状态"""
    sid = sm.create()
    sup = sm.get(sid)
    sup.state = InterviewState.ASKING
    sm.save(sid, sup)

    sup2 = sm.get(sid)
    assert sup2.state == InterviewState.ASKING


def test_get_nonexistent_raises(sm):
    """读不存在的会话抛 KeyError"""
    with pytest.raises(KeyError):
        sm.get("does_not_exist")


def test_drop_removes_session(sm):
    """drop 后会话消失"""
    sid = sm.create()
    sm.drop(sid)
    with pytest.raises(KeyError):
        sm.get(sid)


def test_save_to_dropped_session_raises(sm):
    """对已删除会话 save 应抛 KeyError（防止复活僵尸会话）"""
    sid = sm.create()
    sup = sm.get(sid)
    sm.drop(sid)
    with pytest.raises(KeyError):
        sm.save(sid, sup)
