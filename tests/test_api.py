"""FastAPI 接口 + 状态机集成测试。
关键：mock 掉三个 Agent 实际调用的工具函数，不触发真实 LLM。
mock 路径打在'使用处'(agents.xxx)，不是'定义处'(tools.xxx)。
"""
import pytest
from fastapi.testclient import TestClient

from api import app
from agents.session_manager import session_manager

client = TestClient(app)


# ---------- 假数据 ----------
FAKE_QUESTIONS = [
    {"type": "项目追问", "question": "你的RAG项目怎么做的", "difficulty": "中"},
    {"type": "Java八股", "question": "Redis分布式锁怎么实现", "difficulty": "中"},
]


class FakeScore:
    """模拟 Score dataclass，asdict 能转"""
    def __init__(self):
        self.accuracy = 4
        self.completeness = 3
        self.depth = 4
        self.clarity = 3
        self.total = 3.5
        self.comment = "回答不错，但深度可加强"


@pytest.fixture
def mock_agents(monkeypatch):
    """把三个 Agent 调用的工具函数替换成假实现，避免调真实 LLM。"""
    from core.models import Score

    def fake_generate_questions(resume, jd, total, type_ratio, **kwargs):
        return FAKE_QUESTIONS[:total] if total <= len(FAKE_QUESTIONS) else FAKE_QUESTIONS

    def fake_score_answer(q_type, question, answer, **kwargs):
        return Score(accuracy=4, completeness=3, depth=4, clarity=3,
                     total=3.5, comment="测试评语")

    def fake_generate_review(position, qa_list, **kwargs):
        return "## 复盘报告\n这是测试复盘内容"

    monkeypatch.setattr("agents.interviewer.generate_questions", fake_generate_questions)
    monkeypatch.setattr("agents.scorer.score_answer", fake_score_answer)
    monkeypatch.setattr("agents.reviewer.generate_review", fake_generate_review)


@pytest.fixture(autouse=True)
def clean_sessions():
    """每个测试前后给全局 session_manager 注入干净的内存存储，
    避免依赖真实 Redis、避免测试间互相干扰。"""
    from agents.session_manager import MemoryStore
    session_manager._store = MemoryStore()
    yield
    session_manager._store = MemoryStore()


# ---------- 测试用例 ----------

def test_start_returns_session_and_questions(mock_agents):
    """出题：返回 session_id + 状态'提问中' + 题目列表"""
    resp = client.post("/api/interview/start", json={
        "resume": "3年后端", "jd": "AI工程师",
        "total_questions": 2, "preset": "均衡型",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "session_id" in data
    assert data["state"] == "提问中"
    assert len(data["questions"]) == 2


def test_answer_returns_score(mock_agents):
    """评分：先出题，再答题，返回评分"""
    start = client.post("/api/interview/start", json={
        "resume": "x", "jd": "y", "total_questions": 2, "preset": "均衡型",
    }).json()
    sid = start["session_id"]

    resp = client.post("/api/interview/answer", json={
        "session_id": sid, "q_type": "项目追问",
        "question": "你的RAG项目怎么做的", "answer": "我用了向量检索",
        "is_last": False,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["score"]["total"] == 3.5
    assert data["state"] == "提问中"   # 非最后一题，流转回提问中


def test_answer_with_fake_session_returns_404(mock_agents):
    """用不存在的 session 答题，应返回 404"""
    resp = client.post("/api/interview/answer", json={
        "session_id": "fake_does_not_exist", "q_type": "项目追问",
        "question": "x", "answer": "y", "is_last": False,
    })
    assert resp.status_code == 404


def test_full_flow_to_finished(mock_agents):
    """完整流程：出题 → 答完所有题 → 复盘，状态机走到'已完成'"""
    start = client.post("/api/interview/start", json={
        "resume": "x", "jd": "y", "total_questions": 2, "preset": "均衡型",
    }).json()
    sid = start["session_id"]
    questions = start["questions"]

    # 答两题，第二题 is_last=True
    for i, q in enumerate(questions):
        is_last = (i == len(questions) - 1)
        r = client.post("/api/interview/answer", json={
            "session_id": sid, "q_type": q["type"],
            "question": q["question"], "answer": "我的回答", "is_last": is_last,
        })
        assert r.status_code == 200

    # 复盘
    qa_list = [
        {"order": i + 1, "q_type": q["type"], "question": q["question"],
         "user_answer": "我的回答",
         "score": {"accuracy": 4, "completeness": 3, "depth": 4,
                   "clarity": 3, "total": 3.5, "comment": "x"}}
        for i, q in enumerate(questions)
    ]
    review = client.post("/api/interview/review", json={
        "session_id": sid, "position": "AI工程师", "qa_list": qa_list,
    })
    assert review.status_code == 200
    assert review.json()["state"] == "已完成"
    assert "复盘" in review.json()["report"]


def test_state_endpoint(mock_agents):
    """查状态接口正常工作"""
    start = client.post("/api/interview/start", json={
        "resume": "x", "jd": "y", "total_questions": 2, "preset": "均衡型",
    }).json()
    sid = start["session_id"]

    resp = client.get(f"/api/interview/{sid}/state")
    assert resp.status_code == 200
    assert resp.json()["state"] == "提问中"


def test_state_endpoint_404_for_missing(mock_agents):
    """查不存在的 session 状态，返回 404"""
    resp = client.get("/api/interview/nonexistent/state")
    assert resp.status_code == 404
