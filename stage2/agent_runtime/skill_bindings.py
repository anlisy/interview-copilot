from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


class SkillBindingError(ValueError):
    pass


@dataclass(frozen=True)
class SkillBinding:
    skill_name: str
    allowed_actions: tuple[str, ...]
    purpose: str


_BINDINGS = {
    "question-design": SkillBinding("question-design", ("generate",), "设计主问题"),
    "question-followup": SkillBinding("question-followup", ("followup",), "判断并生成追问"),
    "question-intent": SkillBinding("question-intent", ("generate",), "在出题链路中判断问题意图"),
    "answer-evaluation": SkillBinding("answer-evaluation", ("score",), "评价候选人回答"),
    "interview-review": SkillBinding("interview-review", ("review",), "生成整场复盘"),
    "difficulty-control": SkillBinding("difficulty-control", ("generate",), "控制下一题难度"),
}


def get_skill_binding(skill: Any) -> SkillBinding:
    name = getattr(skill, "name", None) or str(skill)
    try:
        binding = _BINDINGS[str(name)]
    except KeyError as exc:
        raise KeyError(f"未定义 Skill binding: {name}") from exc

    declared = tuple(getattr(skill, "allowed_actions", ()) or ())
    if declared and declared != binding.allowed_actions:
        raise SkillBindingError(
            f"Skill={name} 的 frontmatter allowed_actions={declared} 与运行时 binding={binding.allowed_actions} 不一致"
        )
    return binding


def all_skill_bindings() -> tuple[SkillBinding, ...]:
    return tuple(_BINDINGS.values())


def bindings_cover(skills: Iterable[Any]) -> bool:
    return all(str(getattr(skill, "name", skill)) in _BINDINGS for skill in skills)


def bindings_for_actions(actions: Iterable[str]) -> tuple[SkillBinding, ...]:
    allowed = set(actions)
    return tuple(binding for binding in _BINDINGS.values() if allowed.intersection(binding.allowed_actions))
