from stage6.decision.rule import RuleDecisionEngine
from stage6.decision.schema import DecisionResult, DecisionTask
from stage8.decision_router import OnlineDecisionRouter


class ErrorEngine:
    name = "error"
    def decide(self, task):
        raise RuntimeError("boom")


def test_router_uses_review_without_engine_handoff():
    router = OnlineDecisionRouter(RuleDecisionEngine(), auto_threshold=0.9, review_threshold=0.7)
    task = DecisionTask("x", "skill", "foo", {"a": "foo", "b": "bar"})
    result = router.decide(task, kind="skill")
    assert result.choice == "a"
    assert result.route in {"auto", "review", "fallback"}
    assert result.fallback is False


def test_router_only_falls_back_on_primary_error():
    router = OnlineDecisionRouter(ErrorEngine(), fallback_engine=RuleDecisionEngine())
    task = DecisionTask("x", "skill", "foo", {"a": "foo", "b": "bar"})
    result = router.decide(task, kind="skill")
    assert result.fallback is True
    assert result.engine == "rule"
