"""面试官 Agent：负责出题。独立上下文，只看简历+JD，不接触评分信息。
L2-c: 出题用强模型保质量。
"""
from agents.base import BaseAgent
from tools.question_tools import generate_questions


class InterviewerAgent(BaseAgent):
    name = "interviewer"

    def generate(self, resume: str, jd: str, total: int, type_ratio: dict) -> list:
        """生成面试题列表。L2-c: 把路由的 model_id 传给工具函数。"""
        return generate_questions(resume, jd, total, type_ratio, model_id=self.model_id)
