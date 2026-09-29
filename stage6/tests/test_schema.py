import pytest

from stage6.decision.schema import DecisionTask, DecisionResult


def test_decision_task_validates_closed_set():
    task = DecisionTask("c1", "skill", "继续追问", {"a": "追问", "b": "评分"})
    task.validate()


def test_intent_task_requires_two_questions():
    task = DecisionTask("i1", "intent", {"question_a": "A"}, {"same_intent": "same", "different_intent": "different"})
    with pytest.raises(ValueError, match="question_b"):
        task.validate()


def test_result_rejects_unknown_choice():
    result = DecisionResult("rule", "c1", "skill", "x", {"a": 1.0}, 1.0, 1.0)
    with pytest.raises(ValueError):
        result.validate({"a": "追问"})


def test_result_total_tokens():
    result = DecisionResult("rule", "c1", "skill", "a", {"a": 1.0}, 1.0, 1.0, 10, 5)
    assert result.total_tokens == 15
