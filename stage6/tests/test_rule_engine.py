from stage6.decision.rule import RuleDecisionEngine
from stage6.decision.schema import DecisionTask


def test_rule_routes_skill_using_keyword_metadata():
    task = DecisionTask(
        "skill-1", "skill", "根据回答继续追问 Redis 边界",
        {"question-design": "设计主问题", "question-followup": "继续追问回答和边界"},
        {"rule_keywords": {"question-followup": ["继续追问", "边界"]}},
    )
    result = RuleDecisionEngine().decide(task)
    assert result.choice == "question-followup"
    assert result.input_tokens == 0
