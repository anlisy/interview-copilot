from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from .skill_bindings import SkillBinding, bindings_for_actions, get_skill_binding
from .skill_runtime import SkillRuntime
from .skill_selector import NoSkillMatch, RuleSkillSelector, SkillSelection
from .skill_schema import SkillActivation


class SkillActionMismatch(RuntimeError):
    pass


@dataclass(frozen=True)
class ManagedDecision:
    selection: SkillSelection
    activation: SkillActivation
    allowed_actions: tuple[str, ...]


class ManagedRuntime:
    """Stage 2 managed runtime: Skill selection is placed before Stage 1 Orchestrator.

    Skill provides domain procedure only. Stage 1 Harness remains the final authority for
    Agent/Action/Tool/State/Quota/Timeout enforcement.
    """

    def __init__(self, orchestrator: Any, skills_root: str, *, selector: Any | None = None):
        self.orchestrator = orchestrator
        self.skills = SkillRuntime(skills_root)
        validation_errors = self.skills.validate()
        if validation_errors:
            raise ValueError("Skill registry 校验失败: " + " | ".join(validation_errors))
        self.selector = selector or RuleSkillSelector()

    @property
    def context(self):
        return self.orchestrator.context

    @property
    def harness(self):
        return self.orchestrator.harness

    def resolve_skill(self, goal: str, observations: Mapping[str, Any] | None = None, *, limit: int = 3) -> ManagedDecision:
        candidates = self.skills.resolve(goal, context=dict(observations or {}), limit=limit)
        if not candidates:
            raise NoSkillMatch("没有候选 Skill")
        selection = self.selector.select(candidates)
        activation = self.skills.activate(selection.selected.skill.name)
        binding = get_skill_binding(activation.metadata)
        self._trace_skill_event("skill_selected", selection, activation, binding)
        return ManagedDecision(selection, activation, binding.allowed_actions)

    def decide(
        self,
        goal: str,
        observations: Mapping[str, Any],
        *,
        limit: int = 3,
    ) -> tuple[ManagedDecision | None, dict[str, Any]]:
        # Skill 只约束“它负责的业务动作”。前置动作（例如 INIT -> diagnose）
        # 仍由 Stage 1 Workflow / Harness 负责，不能因为尚未进入 Skill 所属阶段
        # 就把一个合法的 prerequisite action 判成 Skill 冲突。
        stage = self.orchestrator.workflow.stage(self.context.stage)
        stage_skill_bindings = bindings_for_actions(stage.get("allowed_actions", []))
        if not stage_skill_bindings:
            decision = dict(self.orchestrator.decide(goal, dict(observations)))
            decision["skill_status"] = "prerequisite"
            self._trace_prerequisite_decision(decision)
            return None, decision

        try:
            managed = self.resolve_skill(goal, observations, limit=limit)
        except NoSkillMatch as exc:
            decision = dict(self.orchestrator.decide(goal, dict(observations)))
            decision["skill_status"] = "not_matched"
            self.harness.tracer.record(
                {
                    "event": "skill_not_matched",
                    "stage": self.context.stage,
                    "reason_code": "no_skill_match",
                    "error": str(exc),
                    "action": decision.get("action"),
                },
                self.context.session_id,
            )
            return None, decision
        enriched = dict(observations)
        enriched["skill"] = {
            "name": managed.activation.metadata.name,
            "description": managed.activation.metadata.description,
            "allowed_actions": list(managed.allowed_actions),
            "instructions": managed.activation.content,
            "selection_margin": managed.selection.margin,
            "selection_reason": managed.selection.reason_code,
        }
        decision = dict(self.orchestrator.decide(goal, enriched))
        decision["skill_status"] = "selected"
        action = decision.get("action")
        if action not in managed.allowed_actions:
            binding = get_skill_binding(managed.activation.metadata)
            self._trace_skill_event(
                "skill_action_rejected",
                managed.selection,
                managed.activation,
                binding,
                extra={"action": action},
            )
            raise SkillActionMismatch(
                f"Skill={managed.activation.metadata.name} 不允许 action={action}; allowed={managed.allowed_actions}"
            )
        return managed, decision

    def _trace_prerequisite_decision(self, decision: Mapping[str, Any]) -> None:
        self.harness.tracer.record(
            {
                "event": "skill_phase_not_active",
                "stage": self.context.stage,
                "action": decision.get("action"),
                "reason_code": decision.get("reason_code"),
            },
            self.context.session_id,
        )

    def run(
        self,
        managed: ManagedDecision,
        decision: Mapping[str, Any],
        handlers: dict[str, Callable[[], Any]],
        *,
        tool: str | None = None,
        next_stage: str | None = None,
    ) -> Any:
        action = decision.get("action")
        if action not in managed.allowed_actions:
            raise SkillActionMismatch(
                f"Skill={managed.activation.metadata.name} 不允许 action={action}"
            )
        return self.orchestrator.run(dict(decision), handlers, tool=tool, next_stage=next_stage)

    def _trace_skill_event(
        self,
        event: str,
        selection: SkillSelection,
        activation: SkillActivation,
        binding: SkillBinding,
        *,
        extra: dict[str, Any] | None = None,
    ) -> None:
        payload = {
            "event": event,
            "stage": self.context.stage,
            "skill": activation.metadata.name,
            "skill_version": activation.metadata.version,
            "selection_margin": selection.margin,
            "selection_reason": selection.reason_code,
            "allowed_actions": list(binding.allowed_actions),
            "alternative_skills": [x.skill.name for x in selection.alternatives],
        }
        if extra:
            payload.update(extra)
        self.harness.tracer.record(payload, self.context.session_id)
