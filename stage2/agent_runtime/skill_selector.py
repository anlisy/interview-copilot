from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .skill_schema import SkillCandidate


class NoSkillMatch(LookupError):
    """没有达到最小激活证据的 Skill。"""


@dataclass(frozen=True)
class SkillSelection:
    selected: SkillCandidate
    alternatives: tuple[SkillCandidate, ...]
    margin: float
    reason_code: str


class RuleSkillSelector:
    """当前阶段的确定性 Skill 选择器。

    只做小候选集上的最终选择，不替代大规模检索。后续可直接替换为 JEV。
    """

    def __init__(self, *, min_score: float = 0.15):
        if not 0.0 <= min_score <= 1.0:
            raise ValueError("min_score 必须在 [0, 1] 内")
        self.min_score = min_score

    def select(self, candidates: Sequence[SkillCandidate]) -> SkillSelection:
        if not candidates:
            raise NoSkillMatch("没有 Skill 候选")
        ordered = list(candidates)
        top = ordered[0]

        # 至少需要一定语义证据；完全无关任务不能被强行路由到某个 Skill。
        # 低于阈值但有明确 signal / intent 时允许保留，避免中文短任务过严过滤。
        has_explicit_evidence = bool(top.matched_signals or top.matched_intents)
        if top.score < self.min_score and not has_explicit_evidence:
            raise NoSkillMatch(
                f"没有足够证据激活 Skill: top={top.skill.name}, score={top.score:.4f}, min={self.min_score:.4f}"
            )

        second_score = ordered[1].score if len(ordered) > 1 else 0.0
        margin = round(top.score - second_score, 4)
        if len(ordered) == 1:
            reason = "single_candidate"
        elif margin >= 0.15:
            reason = "clear_margin"
        else:
            reason = "close_candidates"
        return SkillSelection(top, tuple(ordered[1:]), margin, reason)
