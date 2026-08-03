"""命令行版模拟面试。直接调用 Supervisor（入口无关），无需 Web 服务。
用法: python cli.py
流程: 简历诊断 → 出题 → 逐题答(含5层追问) → 复盘 → 命中率评估
"""
import sys
import textwrap
from dataclasses import asdict

from agents.supervisor import Supervisor
from tools.eval_tools import evaluate_prediction

PRESETS = {
    "1": ("均衡型", {"RESUME_PROJECT": 30, "RESUME_INTERNSHIP": 15, "JAVA_BASIC": 20,
                    "AI_BASIC": 20, "CODING": 10, "BEHAVIOR": 5}),
    "2": ("重项目型", {"RESUME_PROJECT": 40, "RESUME_INTERNSHIP": 25, "JAVA_BASIC": 10,
                    "AI_BASIC": 15, "CODING": 5, "BEHAVIOR": 5}),
    "3": ("重八股型", {"RESUME_PROJECT": 15, "RESUME_INTERNSHIP": 10, "JAVA_BASIC": 35,
                    "AI_BASIC": 30, "CODING": 5, "BEHAVIOR": 5}),
}
MAX_FOLLOWUP = 2
LINE = "=" * 60


def wrap(text, indent=""):
    for line in textwrap.wrap(str(text), width=54):
        print(indent + line)


def multiline_input(prompt: str) -> str:
    print(prompt + "（输完单独一行输 END 结束）：")
    lines = []
    while True:
        line = input()
        if line.strip() == "END":
            break
        lines.append(line)
    return "\n".join(lines)


def main():
    print(LINE)
    print("  🎯 Interview Copilot —— 命令行模拟面试")
    print(LINE)

    position = input("岗位（默认 AI应用研发工程师）: ").strip() or "AI应用研发工程师"
    resume = multiline_input("\n粘贴简历内容")
    jd = multiline_input("\n粘贴岗位JD")
    if not resume.strip() or not jd.strip():
        print("❌ 简历和JD不能为空")
        sys.exit(1)

    sup = Supervisor()

    # ===== 简历诊断 =====
    print("\n⏳ 面试官正在研判你的简历...")
    diag = sup.interviewer.diagnose(resume, jd)
    print("\n" + LINE)
    print("  🔍 简历诊断报告")
    print(LINE)
    if diag["highlights"]:
        print("🌟 亮点（会被重点问）:")
        for h in diag["highlights"]:
            wrap(f"· {h.get('point','')}", "  ")
            wrap(f"会被追问: {h.get('likely_followup','')}", "    ")
    if diag["risks"]:
        print("⚠️  风险（可能被challenge）:")
        for x in diag["risks"]:
            wrap(f"· {x.get('point','')}: {x.get('challenge','')}", "  ")
    if diag["suggestions"]:
        print("💡 准备建议:")
        for s in diag["suggestions"]:
            wrap(f"· {s}", "  ")

    input("\n按回车开始面试...")

    # ===== 配置 =====
    total = input("\n题目数量（默认 5）: ").strip()
    total = int(total) if total.isdigit() else 5
    print("题型: 1均衡 2重项目 3重八股（默认1）")
    preset_name, type_ratio = PRESETS.get(input("选择: ").strip() or "1", PRESETS["1"])

    # ===== 出题 =====
    print(f"\n⏳ 出题中（{preset_name}）...")
    questions = sup.run_generate(resume, jd, total, type_ratio)
    print(f"✅ 生成 {len(questions)} 道题\n")

    # ===== 逐题答 + 5层追问 =====
    qa_records = []
    for idx, q in enumerate(questions):
        is_last = (idx == len(questions) - 1)
        print(LINE)
        print(f"第 {idx+1}/{len(questions)} 题  【{q.get('type')}|{q.get('difficulty')}】")
        print("-" * 60)
        wrap(q.get("question", ""))
        print("-" * 60)

        answer = multiline_input("你的回答")
        print("⏳ 评分中...")
        score = sup.run_score_only(q.get("type"), q.get("question"), answer)
        print(f"\n📊 得分 {score.total}/5 "
              f"(准确{score.accuracy} 完整{score.completeness} 深度{score.depth} 表达{score.clarity})")
        wrap("💬 " + score.comment)

        fu_count = 0
        followups = []
        while True:
            need, fq, reason = sup.decide_followup(
                q.get("question"), answer, asdict(score), fu_count, MAX_FOLLOWUP)
            if not need:
                break
            sup.go_followup()
            print("\n🔁 追问:")
            wrap(fq, "  ")
            fu_ans = multiline_input("你的追问回答")
            print("⏳ 评分中...")
            fu_score = sup.run_score_only("追问", fq, fu_ans)
            print(f"📊 追问得分 {fu_score.total}/5")
            followups.append({"q": fq, "a": fu_ans})
            fu_count += 1

        sup.go_next_or_finish(is_last)
        qa_records.append({
            "type": q.get("type"), "question": q.get("question"),
            "answer": answer, "score": score, "followups": followups,
        })
        print()

    # ===== 复盘 =====
    print(LINE)
    print("⏳ 生成复盘报告...")
    from core.models import QARecord
    review_input = [
        QARecord(order=i + 1, q_type=r["type"], question=r["question"],
                 user_answer=r["answer"], score=r["score"])
        for i, r in enumerate(qa_records)
    ]
    report = sup.run_review(position, review_input)
    print(LINE)
    print("  📝 复盘报告")
    print(LINE)
    print(report)

    # ===== 命中率 =====
    print("\n" + LINE)
    print("  📊 预测命中率（对比真实面经库）")
    print(LINE)
    try:
        ev = evaluate_prediction([{"question": r["question"]} for r in qa_records])
        print(f"命中率 {ev['hit_rate']*100:.0f}% ({ev['hits']}/{ev['total']}) 阈值{ev['threshold']}")
        for d in ev["details"]:
            flag = "✅" if d["hit"] else "❌"
            wrap(f"{flag}[{d['similarity']:.2f}] {d['question']}", "")
    except Exception as e:
        print(f"（命中率跳过: {e}）")

    valid = [r["score"].total for r in qa_records if r["score"]]
    avg = sum(valid) / len(valid) if valid else 0
    print("\n" + LINE)
    print(f"  🎉 面试完成！总分 {avg:.1f}/5")
    print(LINE)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 已中断")
        sys.exit(0)
