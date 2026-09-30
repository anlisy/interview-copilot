from __future__ import annotations

import argparse
import json
from pathlib import Path

from stage4.memory.memory_store import MemoryStore

from .decision_router import OnlineDecisionRouter, build_decision_engine
from .runtime import OnlineInterviewRuntime
from .stage1_agent_runner import Stage1AgentRunner
from .text_runner import EchoTextRunner, ZhipuTextRunner
from .trace import OnlineTraceRecorder

ROOT = Path(__file__).resolve().parent.parent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Stage8 Online Interview Runtime")
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--agent", default="interviewer", choices=("interviewer", "reviewer", "scorer"))
    parser.add_argument("--action", default="generate", choices=("diagnose", "generate", "followup", "review"))
    parser.add_argument("--engine", default="rule", choices=("rule", "glm", "jev"))
    parser.add_argument("--text-mode", default="echo", choices=("echo", "zhipu"))
    parser.add_argument("--agent-mode", default="text", choices=("text", "stage1"))
    parser.add_argument("--root", default=".agent_memory")
    parser.add_argument("--session-root", default=".agent_sessions")
    parser.add_argument("--trace-root", default="storage/traces/stage8")
    parser.add_argument("--stage7-mode", default="rule", choices=("rule", "glm"))
    parser.add_argument("--auto-threshold", type=float, default=0.90)
    parser.add_argument("--review-threshold", type=float, default=0.70)
    parser.add_argument("--serial-decision", action="store_true")
    parser.add_argument("--finish", action="store_true")
    parser.add_argument("--execute-tool", action="store_true")
    parser.add_argument("--tool-arguments", default="{}")
    parser.add_argument("--eval-mode", action="store_true")
    parser.add_argument("--memory-candidate", action="store_true", help="将本轮 --answer 显式标记为长期记忆候选")
    parser.add_argument("--memory-type", default="verified_experience")
    parser.add_argument("--memory-confidence", type=float, default=0.8)
    parser.add_argument("--memory-importance", type=float, default=0.6)
    parser.add_argument("--resume", default="")
    parser.add_argument("--jd", default="")
    parser.add_argument("--answer", default="")
    parser.add_argument("--question", default="")
    parser.add_argument("--position", default="")
    parser.add_argument("--qa-list", default="[]")
    parser.add_argument("--total", type=int, default=5)
    parser.add_argument("--type-ratio", default="")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        tool_arguments = json.loads(args.tool_arguments)
        qa_list = json.loads(args.qa_list)
        type_ratio = json.loads(args.type_ratio) if args.type_ratio else {"basic": 0.2, "project": 0.5, "scenario": 0.3}
    except json.JSONDecodeError as exc:
        print(json.dumps({"error": f"JSON 参数不合法: {exc}"}, ensure_ascii=False, indent=2))
        return 2
    if not isinstance(qa_list, list):
        print(json.dumps({"error": "--qa-list 必须是 JSON 数组"}, ensure_ascii=False, indent=2))
        return 2
    if not isinstance(type_ratio, dict):
        print(json.dumps({"error": "--type-ratio 必须是 JSON 对象"}, ensure_ascii=False, indent=2))
        return 2

    engine = build_decision_engine(args.engine)
    fallback_engine = build_decision_engine("rule") if args.engine != "rule" else None
    router = OnlineDecisionRouter(
        engine,
        fallback_engine=fallback_engine,
        auto_threshold=args.auto_threshold,
        review_threshold=args.review_threshold,
        fallback_on_error_only=True,
        sanitize_result=True,
    )
    agent_runner = Stage1AgentRunner() if args.agent_mode == "stage1" else None
    # stage1 模式不会走 text runner，因此避免无意义地初始化 Zhipu client。
    runner = EchoTextRunner() if agent_runner is not None or args.text_mode == "echo" else ZhipuTextRunner()
    runtime = OnlineInterviewRuntime(
        memory=MemoryStore(args.root),
        skills_root=ROOT / "stage2" / "skills",
        decision_router=router,
        text_runner=runner,
        agent_runner=agent_runner,
        session_store=__import__("stage8.session_store", fromlist=["FileSessionStateStore"]).FileSessionStateStore(args.session_root),
        trace=OnlineTraceRecorder(args.trace_root),
        stage7_mode=args.stage7_mode,
        decision_parallel=not args.serial_decision,
    )
    try:
        result = runtime.run_turn(
            session_id=args.session_id,
            task=args.task,
            agent=args.agent,
            action=args.action,
            eval_mode=args.eval_mode,
            finish=args.finish,
            profile=args.resume,
            evidence=args.jd,
            resume=args.resume,
            jd=args.jd,
            question=args.question,
            answer=args.answer,
            position=args.position,
            qa_list=qa_list,
            total=args.total,
            type_ratio=type_ratio,
            execute_tool=args.execute_tool,
            tool_arguments=tool_arguments,
            memory_candidate=args.memory_candidate,
            memory_type=args.memory_type,
            memory_confidence=args.memory_confidence,
            memory_importance=args.memory_importance,
        )
    except Exception as exc:
        print(json.dumps({"status": "error", "type": type(exc).__name__, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1

    payload = result.to_dict()
    payload["online_meta"] = {
        "agent_mode": args.agent_mode,
        "decision_parallel": not args.serial_decision,
        "decision_engine": args.engine,
        "text_mode": args.text_mode,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
