"""Interview Copilot CLI：兼容模式 + Agent Runtime 模式。

默认：python cli.py
Agent Runtime：set AGENT_ORCHESTRATOR=1 && python cli.py
"""
import os
import sys
import textwrap
from dataclasses import asdict
from pathlib import Path

# 兼容两种启动方式：
#   python -m stage1.cli
#   python stage1\cli.py
# 项目根目录必须排在 stage1 之前，避免 stage1/core 遮蔽项目自己的 core 包。
ROOT = Path(__file__).resolve().parent.parent
STAGE1_DIR = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(STAGE1_DIR) not in sys.path:
    sys.path.insert(1, str(STAGE1_DIR))

from agents.supervisor import Supervisor
from tools.eval_tools import evaluate_prediction
from agent_runtime.orchestrator import Orchestrator
from agent_runtime.trace import TraceRecorder

PRESETS = {
    "1": ("均衡型", {"RESUME_PROJECT": 30, "RESUME_INTERNSHIP": 15, "JAVA_BASIC": 20, "AI_BASIC": 20, "CODING": 10, "BEHAVIOR": 5}),
    "2": ("重项目型", {"RESUME_PROJECT": 40, "RESUME_INTERNSHIP": 25, "JAVA_BASIC": 10, "AI_BASIC": 15, "CODING": 5, "BEHAVIOR": 5}),
    "3": ("重八股型", {"RESUME_PROJECT": 15, "RESUME_INTERNSHIP": 10, "JAVA_BASIC": 35, "AI_BASIC": 30, "CODING": 5, "BEHAVIOR": 5}),
}
MAX_FOLLOWUP = 2
LINE = "=" * 60


def wrap(text, indent=""):
    for line in textwrap.wrap(str(text), width=54):
        print(indent + line)


def multiline_input(prompt: str) -> str:
    print(prompt + "（输完单独一行 END 结束）：")
    lines = []
    while True:
        line = input()
        if line.strip() == "END":
            return "\n".join(lines)
        lines.append(line)


def build_runtime():
    if os.getenv("AGENT_ORCHESTRATOR", "0") != "1":
        return None
    sid = os.getenv("INTERVIEW_SESSION_ID", "cli")
    eval_mode = os.getenv("EVAL_MODE", "0") == "1"
    return Orchestrator(
        STAGE1_DIR / "core" / "workflow.yaml",
        sid,
        eval_mode=eval_mode,
        tracer=TraceRecorder(ROOT / "storage" / "traces"),
    )


def choose(decider, goal, obs):
    return decider.decide(goal, obs)


def main():
    print(LINE)
    print("  Interview Copilot — Agent Runtime CLI")
    print(LINE)
    position = input("岗位（默认 AI应用研发工程师）: ").strip() or "AI应用研发工程师"
    resume = multiline_input("\n粘贴简历内容")
    jd = multiline_input("\n粘贴岗位JD")
    if not resume.strip() or not jd.strip():
        print("❌ 简历和JD不能为空")
        return 2

    sup = Supervisor()
    runtime = build_runtime()
    print("🧭 Agent Runtime 模式" if runtime else "🧩 Supervisor 兼容模式")

    # 1. 诊断
    print("\n⏳ 面试官正在研判你的简历...")
    if runtime:
        d = choose(runtime, "完成简历诊断", {"resume": resume, "jd": jd})
        diag = runtime.run(d, {"diagnose": lambda: sup.interviewer.diagnose(resume, jd)})
        runtime.harness.transition(runtime.context, "DIAGNOSIS")
    else:
        diag = sup.interviewer.diagnose(resume, jd)

    print("\n" + LINE)
    print("  简历诊断报告")
    print(LINE)
    for h in diag.get("highlights", []):
        wrap(f"· {h.get('point','')}", "  ")
        wrap(f"会被追问: {h.get('likely_followup','')}", "    ")
    for x in diag.get("risks", []):
        wrap(f"· {x.get('point','')}: {x.get('challenge','')}", "  ")
    for s in diag.get("suggestions", []):
        wrap(f"· {s}", "  ")
    input("\n按回车开始面试...")

    total_raw = input("\n题目数量（默认 5）: ").strip()
    total = int(total_raw) if total_raw.isdigit() else 5
    preset_name, type_ratio = PRESETS.get(input("题型: 1均衡 2重项目 3重八股（默认1）: ").strip() or "1", PRESETS["1"])

    # 2. 出题
    print(f"\n⏳ 出题中（{preset_name}）...")
    if runtime:
        d = choose(runtime, "根据简历、JD和诊断生成主问题", {"total": total, "preset": preset_name})
        questions = runtime.run(d, {"generate": lambda: sup.run_generate(resume, jd, total, type_ratio)})
        runtime.harness.transition(runtime.context, "ASKING")
    else:
        questions = sup.run_generate(resume, jd, total, type_ratio)
    print(f"✅ 生成 {len(questions)} 道题")

    qa_records = []
    for idx, q in enumerate(questions):
        is_last = idx == len(questions) - 1
        print("\n" + LINE)
        print(f"第 {idx+1}/{len(questions)} 题")
        print("-" * 60)
        wrap(q.get("question", ""))
        print("-" * 60)
        answer = multiline_input("你的回答")

        if runtime:
            # 评分决策发生在 ASKING/FOLLOWUP，评分执行完成后由 Harness 推进到 SCORING。
            d = choose(runtime, "独立评分当前回答", {"question": q.get("question"), "answer": answer})
            score = runtime.run(
                d,
                {"score": lambda: sup.run_score_only(q.get("type"), q.get("question"), answer)},
                next_stage="SCORING",
            )
        else:
            score = sup.run_score_only(q.get("type"), q.get("question"), answer)

        print(f"\n📊 得分 {score.total}/5")
        wrap("💬 " + score.comment)

        fu_count = 0
        followups = []
        while fu_count < MAX_FOLLOWUP:
            need, fq, reason = sup.decide_followup(q.get("question"), answer, asdict(score), fu_count, MAX_FOLLOWUP)
            if not need:
                break
            sup.go_followup()
            if runtime:
                runtime.harness.transition(runtime.context, "FOLLOWUP")
            print("\n🔁 追问:")
            wrap(fq, "  ")
            fu_ans = multiline_input("你的追问回答")
            if runtime:
                d = choose(runtime, "独立评分追问回答", {"question": fq, "answer": fu_ans})
                fu_score = runtime.run(
                    d,
                    {"score": lambda: sup.run_score_only("追问", fq, fu_ans)},
                    next_stage="SCORING",
                )
            else:
                fu_score = sup.run_score_only("追问", fq, fu_ans)
            print(f"📊 追问得分 {fu_score.total}/5")
            followups.append({"q": fq, "a": fu_ans, "score": fu_score})
            fu_count += 1
            answer = fu_ans
            score = fu_score

        if runtime:
            runtime.harness.transition(runtime.context, "REVIEWING" if is_last else "ASKING")
        sup.go_next_or_finish(is_last)
        qa_records.append({"type": q.get("type"), "question": q.get("question"), "answer": answer, "score": score, "followups": followups})

    # 3. 复盘
    from core.models import QARecord
    print("\n" + LINE)
    print("⏳ 生成复盘报告...")
    review_input = [QARecord(order=i+1, q_type=r["type"], question=r["question"], user_answer=r["answer"], score=r["score"]) for i, r in enumerate(qa_records)]
    if runtime:
        d = choose(runtime, "生成整场面试复盘报告", {
            "position": position,
            "question_count": len(review_input),
            "scores": [getattr(r["score"], "total", None) for r in qa_records],
        })
        report = runtime.run(
            d,
            {"review": lambda: sup.run_review(position, review_input)},
            next_stage="FINISHED",
        )
    else:
        report = sup.run_review(position, review_input)
    print(LINE)
    print(report)

    # 4. 保留旧命中率，作为 Stage 0 指标
    print("\n" + LINE)
    print("  预测题语义命中率（旧指标，暂不作为完整 Agent Eval）")
    print(LINE)
    try:
        ev = evaluate_prediction([{"question": r["question"]} for r in qa_records])
        print(f"命中率 {ev['hit_rate']*100:.0f}% ({ev['hits']}/{ev['total']}) 阈值 {ev['threshold']}")
    except Exception as exc:
        print(f"（命中率跳过: {exc}）")

    valid = [r["score"].total for r in qa_records if r["score"]]
    avg = sum(valid) / len(valid) if valid else 0
    print("\n" + LINE)
    print(f"  面试完成！总分 {avg:.1f}/5")
    print(LINE)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n已中断")
        raise SystemExit(130)
