"""模型路由测试：验证每个 Agent 路由到正确的模型（不真调 LLM）"""
from core.config import get_model_for_agent, AGENT_MODEL_ROUTING


def test_routing_table_has_three_agents():
    assert "interviewer" in AGENT_MODEL_ROUTING
    assert "scorer" in AGENT_MODEL_ROUTING
    assert "reviewer" in AGENT_MODEL_ROUTING


def test_interviewer_uses_strong_model():
    assert get_model_for_agent("interviewer") == "glm-4-plus"


def test_scorer_uses_fast_model():
    assert get_model_for_agent("scorer") == "glm-4-flash"


def test_reviewer_uses_mid_model():
    assert get_model_for_agent("reviewer") == "glm-4-air"


def test_unknown_agent_falls_back_to_default():
    from core.config import MODEL_ID
    assert get_model_for_agent("unknown_agent") == MODEL_ID


def test_agents_have_correct_model_id():
    from agents.interviewer import InterviewerAgent
    from agents.scorer import ScorerAgent
    from agents.reviewer import ReviewerAgent
    assert InterviewerAgent().model_id == "glm-4-plus"
    assert ScorerAgent().model_id == "glm-4-flash"
    assert ReviewerAgent().model_id == "glm-4-air"
