from core.config import ROOT
from core.models import InterviewConfig
from tools.question_tools import generate_questions

resume = (ROOT / "data" / "resume_example.txt").read_text(encoding="utf-8")
jd = (ROOT / "data" / "jd_example.txt").read_text(encoding="utf-8")

config = InterviewConfig(total_questions=5)  # 先生成5题测试

print("正在出题...")
questions = generate_questions(resume, jd, config.total_questions, config.type_ratio)

print(f"\n共生成 {len(questions)} 道题：\n")
for i, q in enumerate(questions, 1):
    print(f"{i}. [{q.get('type','?')}|{q.get('difficulty','?')}] {q.get('question','')}\n")
