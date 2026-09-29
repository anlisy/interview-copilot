from types import SimpleNamespace

from stage6.decision.skill_selector import DecisionSkillSelector
from stage6.decision.schema import DecisionResult


class FakeEngine:
    def decide(self, task):
        return DecisionResult(
            engine="fake",
            task_id=task.task_id,
            task_type=task.task_type,
            choice="question-followup",
            probabilities={"question-followup":0.9,"question-design":0.1},
            confidence=0.9,
            latency_ms=1,
        )


def test_stage2_candidate_adapter_selects_decision():
    skill = lambda name, desc: SimpleNamespace(skill=SimpleNamespace(name=name, description=desc), score=0.5)
    candidates = [skill("question-design", "设计主问题"), skill("question-followup", "根据回答继续追问")]
    selection = DecisionSkillSelector(FakeEngine()).select(candidates, task_text="继续追问")
    assert selection.selected.skill.name == "question-followup"
    assert selection.confidence == 0.9
    assert selection.route == "auto"
