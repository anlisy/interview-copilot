from __future__ import annotations

import re
from dataclasses import replace
from typing import Iterable

from .skill_registry import SkillRegistry
from .skill_schema import SkillCandidate, SkillMetadata


class SkillResolver:
    """轻量规则路由器：负责候选 Skill 召回与确定性排序。

    这里不使用大模型，也不训练 JEV。后续可以把最终选择器替换为 JEV，
    而保持 `resolve()` 的候选集接口不变。
    """

    def __init__(self, registry: SkillRegistry):
        self.registry = registry

    def metadata(self) -> list[SkillMetadata]:
        return self.registry.discover()

    def resolve(
        self,
        task: str,
        *,
        context: dict[str, object] | None = None,
        limit: int = 3,
    ) -> list[SkillCandidate]:
        if limit <= 0:
            return []
        query_terms = _terms(task)
        query_phrases = _phrases(task)
        intents = _context_intents(context or {})
        results: list[SkillCandidate] = []
        for skill in self.metadata():
            signal_terms = set().union(*(_terms(s) for s in skill.signals)) if skill.signals else set()
            name_desc_terms = _terms(skill.name + " " + skill.description)
            matched_signals = tuple(sorted(s for s in skill.signals if _phrase_hit(s, task)))
            matched_intents = tuple(sorted(i for i in skill.intents if i in intents))
            signal_overlap = len(query_terms & signal_terms) / max(1, len(query_terms))
            desc_overlap = len(query_terms & name_desc_terms) / max(1, len(query_terms))
            phrase_hits = sum(1 for p in skill.signals if p in query_phrases or _phrase_hit(p, task))
            intent_bonus = min(1.0, len(matched_intents) * 0.25)
            context_intent_boost = 0.25 if intents and matched_intents else 0.0
            score = min(1.0, 0.50 * signal_overlap + 0.20 * desc_overlap + 0.15 * min(1.0, phrase_hits / 2) + 0.10 * intent_bonus + context_intent_boost)
            reason = "signal_match" if matched_signals else ("description_match" if desc_overlap > 0 else "fallback")
            results.append(SkillCandidate(skill, round(score, 4), matched_signals, matched_intents, reason))
        results.sort(key=lambda x: (-x.score, x.skill.name))
        picked = results[:limit]
        if picked and picked[0].score == 0:
            picked = [replace(picked[0], reason_code="fallback")]
        return picked


def _terms(text: str) -> set[str]:
    normalized = (text or "").lower()
    out = set(re.findall(r"[a-z0-9_]+", normalized))
    cjk = re.findall(r"[\u4e00-\u9fff]+", normalized)
    for chunk in cjk:
        out.update(chunk[i:i + 2] for i in range(len(chunk) - 1))
        out.update(chunk)
    return {x for x in out if x}


def _phrases(text: str) -> set[str]:
    return {x.strip().lower() for x in re.split(r"[，,、。！？?；;：:\s]+", text or "") if x.strip()}


def _phrase_hit(signal: str, task: str) -> bool:
    signal = signal.lower().strip()
    task = task.lower()
    return bool(signal) and signal in task


def _context_intents(context: dict[str, object]) -> set[str]:
    raw = context.get("intent") or context.get("intents") or ()
    if isinstance(raw, str):
        return {raw.lower()}
    try:
        return {str(x).lower() for x in raw}  # type: ignore[union-attr]
    except TypeError:
        return set()
