from tools.score_tools import score_answer

q_type = "Java八股"
question = "请解释 Java 线程池中 corePoolSize、maximumPoolSize 和 workQueue 的配合机制。如果队列已满且线程数达到最大值，新任务会执行什么操作？"

# 模拟一个回答（你可以换成自己的真实回答测试）
answer = """corePoolSize 是核心线程数，线程池会一直保留这些线程。
新任务来了先用核心线程，核心线程满了就放进 workQueue 队列。
队列也满了，才会创建新线程直到 maximumPoolSize。
如果线程数达到最大值且队列也满了，就会触发拒绝策略，比如默认的 AbortPolicy 会抛 RejectedExecutionException。"""

print("正在打分...")
score = score_answer(q_type, question, answer)

print(f"\n准确性: {score.accuracy}/5")
print(f"完整性: {score.completeness}/5")
print(f"技术深度: {score.depth}/5")
print(f"表达清晰度: {score.clarity}/5")
print(f"总分: {score.total}/5")
print(f"\n评语: {score.comment}")
