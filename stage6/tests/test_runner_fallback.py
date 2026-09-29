from stage6.benchmark.runner import run_engine
from stage6.decision.rule import RuleDecisionEngine
from stage6.decision.schema import DecisionResult
from stage6.decision.base import DecisionEngine


class LowConfidenceEngine(DecisionEngine):
    name = "low"

    def _decide(self, task):
        return DecisionResult(
            engine=self.name, task_id=task.task_id, task_type=task.task_type, choice="wrong",
            probabilities={"wrong":0.6,"right":0.4}, confidence=0.4, latency_ms=1.0
        )


def test_fallback_replaces_effective_choice():
    cases = [{
        "id":"c1","task_type":"skill","state":"right",
        "options":{"wrong":"wrong","right":"right"},"expected":"right"
    }]
    rows = run_engine(LowConfidenceEngine(), cases, fallback_engine=RuleDecisionEngine())
    assert rows[0]["raw_predicted"] == "wrong"
    assert rows[0]["effective_predicted"] == "right"
    assert rows[0]["fallback_applied"] is True
