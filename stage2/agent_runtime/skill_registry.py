from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .frontmatter import SkillFormatError, split_frontmatter, validate_frontmatter
from .skill_schema import SkillMetadata


class SkillRegistry:
    """只负责发现与校验 Skill，不负责决定何时激活。"""

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        if not self.root.exists():
            raise FileNotFoundError(self.root)

    def skill_dirs(self) -> list[Path]:
        return sorted(p for p in self.root.iterdir() if p.is_dir() and (p / "SKILL.md").is_file())

    def read_metadata(self, skill_dir: Path) -> SkillMetadata:
        skill_file = (skill_dir / "SKILL.md").resolve()
        if self.root not in skill_file.parents:
            raise SkillFormatError("Skill 路径越界")
        text = skill_file.read_text(encoding="utf-8")
        frontmatter, _ = split_frontmatter(text)
        errors = validate_frontmatter(frontmatter, skill_dir_name=skill_dir.name)
        if errors:
            raise SkillFormatError(f"{skill_file}: " + "; ".join(errors))
        metadata = frontmatter.get("metadata") or {}
        signals = _tuple_values(metadata.get("signals", ()))
        intents = _tuple_values(metadata.get("intents", ()))
        allowed_actions = _tuple_values(metadata.get("allowed_actions", ()))
        version = str(metadata.get("version", "1.0"))
        return SkillMetadata(
            name=str(frontmatter["name"]).strip(),
            description=str(frontmatter["description"]).strip(),
            path=skill_file,
            signals=signals,
            intents=intents,
            allowed_actions=allowed_actions,
            version=version,
            extra={k: v for k, v in metadata.items() if k not in {"signals", "intents", "version"}},
        )

    def discover(self) -> list[SkillMetadata]:
        return [self.read_metadata(path) for path in self.skill_dirs()]

    def validate_all(self) -> list[str]:
        errors: list[str] = []
        names: set[str] = set()
        for path in self.skill_dirs():
            try:
                meta = self.read_metadata(path)
            except (OSError, SkillFormatError) as exc:
                errors.append(str(exc))
                continue
            if meta.name in names:
                errors.append(f"重复 Skill 名称: {meta.name}")
            names.add(meta.name)
            text = meta.path.read_text(encoding="utf-8")
            line_count = len(text.splitlines())
            if line_count > 500:
                errors.append(f"{meta.name}: SKILL.md 超过 500 行，建议拆到 references/")
            for heading in ("# 目标", "## 适用场景", "## 输出", "## 失败处理"):
                if heading not in text:
                    errors.append(f"{meta.name}: 缺少必要章节 {heading}")
            try:
                from .skill_bindings import get_skill_binding
                get_skill_binding(meta)
            except Exception as exc:
                errors.append(f"{meta.name}: Skill binding 不一致: {exc}")
        return errors


def _tuple_values(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return tuple(x.strip().lower() for x in value.split(",") if x.strip())
    if isinstance(value, Iterable):
        return tuple(str(x).strip().lower() for x in value if str(x).strip())
    return ()
