from core.models import QARecord, Score
from tools.review_tools import generate_review

# 模拟一场只有2题的面试记录
qa_list = [
    QARecord(
        order=1, q_type="Java八股",
        question="解释线程池 corePoolSize/maximumPoolSize/workQueue 的配合机制",
        user_answer="核心线程先用，满了进队列，队列满了创建新线程到最大值，再满触发拒绝策略。",
        score=Score(5, 4, 4, 5, 4.5, "回答准确清晰，但遗漏了线程回收机制和不同队列类型的影响。"),
    ),
    QARecord(
        order=2, q_type="AI应用八股",
        question="除了RAG，还有哪些手段降低大模型幻觉？",
        user_answer="可以用提示词约束，让它不知道就说不知道。",
        score=Score(3, 2, 2, 3, 2.5, "回答过于简单，只提到提示词，遗漏了引用溯源、输出校验、温度调节、多次采样投票等工程手段。"),
    ),
]

print("正在生成复盘报告...\n")
report = generate_review("AI应用研发工程师", qa_list)
print(report)
