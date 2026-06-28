"""验证 Supervisor 串起三个 Agent 的完整流程（带计时与进度）"""
import time
from core.config import ROOT
from core.models import InterviewConfig, QARecord
from agents.supervisor import Supervisor

resume = (ROOT / "data" / "resume_example.txt").read_text(encoding="utf-8")
jd = (ROOT / "data" / "jd_example.txt").read_text(encoding="utf-8")

sup = Supervisor()
config = InterviewConfig(total_questions=3)

# 1. 出题
print(f"[状态] {sup.state.value} -> 开始出题")
t0 = time.time()
questions = sup.run_generate(resume, jd, config.total_questions, config.type_ratio)
print(f"[状态] {sup.state.value}，共 {len(questions)} 题，出题耗时 {time.time()-t0:.1f}s\n")

# 2. 逐题模拟回答 + 评分
qa_list = []
for i, q in enumerate(questions):
    is_last = (i == len(questions) - 1)
    answer = "这是我的模拟回答，简单说一下我的理解。"
    print(f"  → 正在评分第 {i+1}/{len(questions)} 题...", flush=True)
    ts = time.time()
    score = sup.run_score(q["type"], q["question"], answer, is_last)
    print(f"  第{i+1}题评分: {score.total}/5  耗时 {time.time()-ts:.1f}s  状态: {sup.state.value}")
    qa_list.append(QARecord(
        order=i + 1, q_type=q["type"], question=q["question"],
        user_answer=answer, score=score,
    ))

# 3. 复盘
print(f"\n[状态] {sup.state.value} -> 开始复盘")
tr = time.time()
report = sup.run_review("AI应用研发工程师", qa_list)
print(f"[状态] {sup.state.value}，复盘耗时 {time.time()-tr:.1f}s")
print(f"\n★ 全流程总耗时 {time.time()-t0:.1f}s\n")
print("复盘报告（前300字）:")
print(report[:300])
