from __future__ import annotations

import argparse
import os
from pathlib import Path

from stage1.agent_runtime.orchestrator import Orchestrator
from stage1.agent_runtime.trace import TraceRecorder

from .agent_runtime.managed_runtime import ManagedRuntime, SkillActionMismatch

ROOT = Path(__file__).resolve().parent.parent
STAGE2_DIR = Path(__file__).resolve().parent


def main() -> int:
    ap = argparse.ArgumentParser(description="Interview Copilot Stage 2 Managed Runtime")
    ap.add_argument("--task", required=True)
    ap.add_argument("--session", default="stage2-managed")
    ap.add_argument("--skill-root", default=str(STAGE2_DIR / "skills"))
    ap.add_argument(
        "--start-stage",
        default="DIAGNOSIS",
        choices=("INIT", "DIAGNOSIS", "ASKING", "SCORING", "FOLLOWUP", "REVIEWING"),
        help="Managed Skill smoke 的起始 Workflow 阶段；默认从 DIAGNOSIS 进入 Skill-owned action。",
    )
    args = ap.parse_args()

    workflow = ROOT / "stage1" / "core" / "workflow.yaml"
    trace_root = ROOT / "storage" / "traces"
    orchestrator = Orchestrator(
        workflow,
        args.session,
        tracer=TraceRecorder(trace_root),
        eval_mode=os.getenv("EVAL_MODE", "0") == "1",
    )
    orchestrator.context.stage = args.start_stage
    runtime = ManagedRuntime(orchestrator, args.skill_root)

    print("🧩 Stage 2 Managed Runtime")
    print("起始阶段:", orchestrator.context.stage)
    print("任务:", args.task)
    try:
        managed, decision = runtime.decide(args.task, {})
    except SkillActionMismatch as exc:
        print("❌ Skill 与 Agent action 不匹配:", exc)
        return 3
    except Exception as exc:
        print("❌ Managed Runtime 失败:", exc)
        return 4

    if managed is None:
        status = decision.get("skill_status")
        if status == "not_matched":
            print("ℹ️ 没有达到 Skill 激活证据，回退到基础 Orchestrator；不会伪造 Skill")
        else:
            print("ℹ️ 当前阶段是前置动作阶段，Skill 尚未激活")
        print(f"🤖 Agent: {decision.get('agent')}")
        print(f"⚙️ Action: {decision.get('action')}")
        print(f"🧾 Reason: {decision.get('reason_code')}")
        return 0

    print(f"🎯 Skill: {managed.activation.metadata.name}")
    print(f"   margin={managed.selection.margin:.4f} reason={managed.selection.reason_code}")
    print(f"   allowed_actions={list(managed.allowed_actions)}")
    print(f"🤖 Agent: {decision.get('agent')}")
    print(f"⚙️ Action: {decision.get('action')}")
    print(f"🧾 Reason: {decision.get('reason_code')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
