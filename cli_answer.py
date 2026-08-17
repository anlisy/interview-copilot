"""答题助手：输入问题清单，RAG检索知识库生成参考答案。
用法: python cli_answer.py
"""
import sys
from datetime import datetime
from core.config import ROOT
from tools.answer_tools import answer_batch


def main():
    print("=" * 50)
    print("  💡 答题助手 —— 基于知识库生成参考答案")
    print("=" * 50)
    print("\n粘贴问题清单，每行一个问题（输完单独一行输 END）：")

    questions = []
    while True:
        line = input()
        if line.strip() == "END":
            break
        line = line.strip()
        # 去掉可能的编号前缀（如 "1. " "- "）
        for prefix in ["- ", "* "]:
            if line.startswith(prefix):
                line = line[len(prefix):]
        if line and line[0].isdigit() and "." in line[:4]:
            line = line.split(".", 1)[1].strip()
        if line:
            questions.append(line)

    if not questions:
        print("❌ 没有输入问题")
        sys.exit(1)

    print(f"\n⏳ 共 {len(questions)} 个问题，逐个生成参考答案...\n")

    def show(idx, total, r):
        tag = "📚基于知识库" if r["source"] == "kb" else "🤖AI生成(仅供参考)"
        print(f"[{idx}/{total}] {tag}")
        print(f"Q: {r['question']}")
        print(f"A: {r['answer']}\n")
        print("-" * 50)

    results = answer_batch(questions, on_answer=show)

    # 生成文档
    lines = [f"# 面试参考答案\n\n生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"]
    for i, r in enumerate(results, 1):
        tag = "📚 基于知识库" if r["source"] == "kb" else "🤖 AI生成（知识库无对应，仅供参考）"
        lines.append(f"\n## {i}. {r['question']}\n")
        lines.append(f"> {tag}\n")
        lines.append(r["answer"])
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = ROOT / "data" / f"参考答案_{ts}.md"
    out.write_text("\n".join(lines), encoding="utf-8")

    print(f"\n✅ 完成！文档已保存: {out}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 已中断")
        sys.exit(0)
