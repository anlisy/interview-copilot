from __future__ import annotations

import argparse
from pathlib import Path

from .agent_runtime.skill_runtime import SkillRuntime
from .agent_runtime.skill_selector import RuleSkillSelector


ROOT = Path(__file__).resolve().parent
SKILLS = ROOT / "skills"


def main() -> int:
    ap = argparse.ArgumentParser(description="Interview Copilot Stage 2 Skill Router")
    ap.add_argument("--task", required=True, help="当前面试任务")
    ap.add_argument("--limit", type=int, default=3)
    args = ap.parse_args()

    runtime = SkillRuntime(SKILLS)
    errors = runtime.registry.validate_all()
    if errors:
        print("❌ Skill 校验失败")
        for error in errors:
            print("  -", error)
        return 2

    print("🧩 Interview Skills")
    print("任务:", args.task)
    candidates = runtime.resolve(args.task, limit=args.limit)
    if not candidates:
        print("❌ 没有匹配 Skill")
        return 3
    print("\n候选 Skill:")
    for i, c in enumerate(candidates, 1):
        print(f"  {i}. {c.skill.name} score={c.score:.4f} reason={c.reason_code}")
        if c.matched_signals:
            print("     signals:", ", ".join(c.matched_signals))
    selection = RuleSkillSelector().select(candidates)
    print(f"\n🎯 选择: {selection.selected.skill.name} margin={selection.margin:.4f} reason={selection.reason_code}")
    activation = runtime.activate(selection.selected.skill.name)
    print(f"✅ 激活: {activation.metadata.name}")
    print("--- skill instructions ---")
    print(activation.content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
