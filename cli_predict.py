"""面试题预测器：只出题+预判追问，生成'可能被问的问题'文档，不需答题。
用法: python cli_predict.py
"""
import sys
from datetime import datetime
from core.config import ROOT
from tools.predict_tools import predict_interview

TYPES = ["项目追问", "实习追问", "Java八股", "AI应用八股", "编程题", "行为问题"]


def multiline_input(prompt: str) -> str:
    print(prompt + "（输完单独一行输 END 结束）：")
    lines = []
    while True:
        line = input()
        if line.strip() == "END":
            break
        lines.append(line)
    return "\n".join(lines)


def ask_int(prompt: str, default: int = 0) -> int:
    v = input(f"{prompt}（默认{default}）: ").strip()
    return int(v) if v.isdigit() else default


def main():
    print("=" * 50)
    print("  🔮 面试题预测器 —— 生成可能被问的问题清单")
    print("=" * 50)

    position = input("岗位（默认 AI应用研发工程师）: ").strip() or "AI应用研发工程师"
    resume = multiline_input("\n粘贴简历")
    jd = multiline_input("\n粘贴JD")
    if not resume.strip() or not jd.strip():
        print("❌ 简历和JD不能为空")
        sys.exit(1)

    # 各类型题数
    print("\n设置各题型数量（0 表示不出）：")
    type_counts = {t: ask_int(f"  {t}", 0) for t in TYPES}
    if sum(type_counts.values()) == 0:
        print("❌ 至少出1题")
        sys.exit(1)

    with_coverage = input("\n生成覆盖率报告?(检查有无遗漏你的经历) y/n: ").strip().lower() == "y"
    with_hit_rate = input("生成命中率报告?(对比真实面经) y/n: ").strip().lower() == "y"

    print("\n⏳ 正在出题...")

    def show_questions(qs):
        print(f"\n✅ 已出 {len(qs)} 道题，开始逐题生成预判追问：\n")

    def show_item(idx, total, item):
        print(f"[{idx}/{total}] 【{item['type']}】{item['question']}")
        for fu in item["followups"]:
            print(f"    └ 追问: {fu}")
        print()

    result = predict_interview(resume, jd, type_counts,
                              with_coverage=with_coverage,
                              with_hit_rate=with_hit_rate,
                              on_questions=show_questions,
                              on_item=show_item)

    # 生成 markdown
    md = generate_markdown(position, result, with_coverage, with_hit_rate)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = ROOT / "data" / f"预测面试题_{ts}.md"
    out.write_text(md, encoding="utf-8")

    print("\n" + "=" * 50)
    print(f"✅ 已生成 {result['total']} 道题及预判追问")
    print(f"📄 文档已保存: {out}")
    if with_hit_rate and "hit_rate" in result:
        hr = result["hit_rate"]
        print(f"📊 命中率: {hr['hit_rate']*100:.0f}% ({hr['hits']}/{hr['total']})")
    if with_coverage and result.get("coverage"):
        cov = result["coverage"]
        print(f"📋 覆盖率: {cov.get('coverage_rate',0)*100:.0f}%")
    print("=" * 50)


def generate_markdown(position, result, with_coverage, with_hit_rate) -> str:
    lines = [f"# 面试预测题清单 - {position}",
             f"\n生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
             f"\n共 {result['total']} 道题\n"]

    # 按题型分组
    by_type = {}
    for q in result["questions"]:
        by_type.setdefault(q["type"], []).append(q)

    for qtype, qs in by_type.items():
        lines.append(f"\n## {qtype} ({len(qs)}题)\n")
        for i, q in enumerate(qs, 1):
            lines.append(f"### {i}. {q['question']}")
            if q["followups"]:
                lines.append("\n**预判追问：**")
                for fu in q["followups"]:
                    lines.append(f"- {fu}")
            lines.append("")

    # 覆盖率报告
    if with_coverage and result.get("coverage"):
        cov = result["coverage"]
        lines.append("\n## 📋 覆盖率报告\n")
        lines.append(f"覆盖率: {cov.get('coverage_rate',0)*100:.0f}%")
        lines.append(f"- 简历技术点: {', '.join(cov.get('all_points',[]))}")
        lines.append(f"- 已覆盖: {', '.join(cov.get('covered',[]))}")
        if cov.get("uncovered"):
            lines.append(f"- ⚠️ 未覆盖: {', '.join(cov['uncovered'])}")

    # 命中率报告
    if with_hit_rate and "hit_rate" in result:
        hr = result["hit_rate"]
        lines.append("\n## 📊 命中率报告\n")
        lines.append(f"命中率: {hr['hit_rate']*100:.0f}% ({hr['hits']}/{hr['total']})")
        lines.append("> 注：命中率仅反映面经库已覆盖方向的题，未覆盖方向不代表题目质量差")
        lines.append("")
        for d in hr["details"]:
            flag = "✅命中" if d["hit"] else "○未命中"
            lines.append(f"- {flag} [{d['similarity']:.2f}] {d['question'][:40]}")

    return "\n".join(lines)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 已中断")
        sys.exit(0)
