from __future__ import annotations

from pathlib import Path

from .frontmatter import SkillFormatError, split_frontmatter
from .skill_registry import SkillRegistry
from .skill_resolver import SkillResolver
from .skill_schema import SkillActivation, SkillCandidate


class SkillRuntime:
    """实现 progressive disclosure：发现只读 metadata，激活时才加载全文。"""

    def __init__(self, skills_root: str | Path):
        self.registry = SkillRegistry(skills_root)
        self.resolver = SkillResolver(self.registry)

    def discover(self):
        return self.registry.discover()

    def resolve(self, task: str, *, context=None, limit: int = 3) -> list[SkillCandidate]:
        return self.resolver.resolve(task, context=context, limit=limit)

    def validate(self) -> list[str]:
        return self.registry.validate_all()

    def activate(self, name: str) -> SkillActivation:
        meta = next((x for x in self.registry.discover() if x.name == name), None)
        if meta is None:
            raise KeyError(f"Skill 不存在: {name}")
        root = self.registry.root.resolve()
        skill_dir = meta.path.parent.resolve()
        if root not in skill_dir.parents:
            raise SkillFormatError("Skill 路径越界")
        text = meta.path.read_text(encoding="utf-8")
        _, body = split_frontmatter(text)
        if not body.strip():
            raise SkillFormatError(f"Skill {name} 的 SKILL.md 正文为空")
        return SkillActivation(metadata=meta, content=body, skill_dir=skill_dir)

    def resolve_and_activate(self, task: str, *, context=None) -> tuple[list[SkillCandidate], SkillActivation]:
        candidates = self.resolve(task, context=context)
        if not candidates:
            raise LookupError("没有可用 Skill")
        return candidates, self.activate(candidates[0].skill.name)
