from __future__ import annotations

import re
from typing import Any


class SkillFormatError(ValueError):
    pass


_NAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    raw = text.lstrip("\ufeff")
    if not raw.startswith("---"):
        raise SkillFormatError("SKILL.md 必须以 YAML frontmatter 开始")
    lines = raw.splitlines()
    if len(lines) < 3 or lines[0].strip() != "---":
        raise SkillFormatError("frontmatter 格式错误")
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        raise SkillFormatError("frontmatter 缺少结束标记 ---")
    fm = _parse_simple_yaml(lines[1:end])
    body = "\n".join(lines[end + 1:]).strip()
    return fm, body


def _parse_simple_yaml(lines: list[str]) -> dict[str, Any]:
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise SkillFormatError("Stage 2 需要 PyYAML 解析 SKILL.md frontmatter") from exc
    block = "\n".join(lines)
    data = yaml.safe_load(block) or {}
    if not isinstance(data, dict):
        raise SkillFormatError("frontmatter 必须是 mapping")
    return data


def validate_frontmatter(data: dict[str, Any], *, skill_dir_name: str | None = None) -> list[str]:
    errors: list[str] = []
    name = data.get("name")
    description = data.get("description")
    if not isinstance(name, str) or not name.strip():
        errors.append("缺少 name")
    else:
        name = name.strip()
        if len(name) > 64:
            errors.append("name 超过 64 字符")
        if not _NAME_RE.fullmatch(name):
            errors.append("name 必须使用小写字母、数字和连字符，且不能以连字符开头/结尾")
        if skill_dir_name and name != skill_dir_name:
            errors.append(f"name 与目录名不一致: {name} != {skill_dir_name}")
    if not isinstance(description, str) or not description.strip():
        errors.append("缺少非空 description")
    elif len(description) > 1024:
        errors.append("description 超过 1024 字符")
    metadata = data.get("metadata", {})
    if metadata is not None and not isinstance(metadata, dict):
        errors.append("metadata 必须是 mapping")
    allowed_tools = data.get("allowed-tools")
    if allowed_tools is not None and not isinstance(allowed_tools, str):
        errors.append("allowed-tools 必须是 space-separated string")
    for key in ("signals", "intents", "allowed_actions"):
        value = metadata.get(key)
        if value is None:
            continue
        if isinstance(value, str):
            continue
        if not isinstance(value, (list, tuple)) or not all(isinstance(x, str) for x in value):
            errors.append(f"metadata.{key} 必须是 string 或 string list")
    return errors
