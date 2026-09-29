from __future__ import annotations

from stage2.agent_runtime.managed_runtime import ManagedRuntime
from stage2.agent_runtime.skill_bindings import get_skill_binding
from stage2.agent_runtime.skill_selector import SkillSelection

from stage6.decision.skill_selector import DecisionSkillSelector


class DecisionManagedRuntime(ManagedRuntime):
    """Stage2 ManagedRuntime variant that lets DecisionEngine see the original goal.

    Stage2 candidate generation, Skill activation, action contract, Orchestrator and Harness
    remain unchanged. Only the final candidate selection is delegated to Stage6.
    """

    def __init__(self, orchestrator, skills_root: str, *, decision_engine, min_confidence: float = 0.70):
        super().__init__(orchestrator, skills_root, selector=None)
        self.decision_selector = DecisionSkillSelector(decision_engine, min_confidence=min_confidence)

    def resolve_skill(self, goal, observations=None, *, limit: int = 3):
        candidates = self.skills.resolve(goal, context=dict(observations or {}), limit=limit)
        if not candidates:
            raise LookupError("没有候选 Skill")
        selected = self.decision_selector.select(candidates, task_text=goal)
        activation = self.skills.activate(selected.selected.skill.name)
        binding = get_skill_binding(selected.selected.skill.name)
        selection = SkillSelection(
            selected=selected.selected,
            alternatives=selected.alternatives,
            margin=selected.margin,
            reason_code=f"decision_{selected.route}",
        )
        self._trace_skill_event("skill_selected", selection, activation, binding, extra={"decision_confidence": selected.confidence})
        return type("ManagedDecisionProxy", (), {
            "selection": selection,
            "activation": activation,
            "allowed_actions": binding.allowed_actions,
        })()
