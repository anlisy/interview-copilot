from stage6.decision.schema import DecisionResult, DecisionTask
from stage8.decision_router import OnlineDecisionRouter


class FixedEngine:
    name = "glm"

    def __init__(self, result):
        self.result = result

    def decide(self, task):
        return self.result


def test_online_router_corrects_choice_probability_mismatch():
    task = DecisionTask("x", "skill", "redis", {"question-design": "出题", "interview-review": "复盘"})
    result = DecisionResult(
        engine="glm",
        task_id="x",
        task_type="skill",
        choice="interview-review",
        probabilities={"question-design": 1.0, "interview-review": 0.0},
        confidence=0.0,
        latency_ms=1.0,
    )
    out = OnlineDecisionRouter(FixedEngine(result), auto_threshold=0.9, review_threshold=0.7).decide(task, kind="skill")
    assert out.choice == "question-design"
    assert out.confidence == 1.0
    assert out.metadata["raw_choice"] == "interview-review"
    assert out.metadata["effective_choice"] == "question-design"


def test_online_router_does_not_force_tied_tool_choice():
    task = DecisionTask("x", "tool", "redis", {"none": "无需工具", "memory_search": "查记忆"})
    result = DecisionResult(
        engine="glm",
        task_id="x",
        task_type="tool",
        choice="none",
        probabilities={"none": 0.5, "memory_search": 0.5},
        confidence=0.0,
        latency_ms=1.0,
    )
    out = OnlineDecisionRouter(FixedEngine(result), auto_threshold=0.9, review_threshold=0.7).decide(task, kind="tool")
    assert out.choice == "none"
    assert out.confidence == 0.5
