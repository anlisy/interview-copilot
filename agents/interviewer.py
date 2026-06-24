"""面试官 Agent：负责出题。独立上下文，只看简历+JD，不接触评分信息。"""
from agents.base import BaseAgent
from tools.question_tools import generate_questions


class InterviewerAgent(BaseAgent):
    name = "interviewer"

    def generate(self, resume: str, jd: str, total: int, type_ratio: dict) -> list:
        """生成面试题列表。内部复用 L1 的工具函数，但归属于本 Agent 的上下文。"""
        return generate_questions(resume, jd, total, type_ratio)
