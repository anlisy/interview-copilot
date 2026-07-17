"""面试官 Agent：负责出题 + 追问决策。
独立上下文，只看简历+JD和当前问答，不接触评分逻辑（评估隔离）。
L2-c: 出题用强模型。L3-a: 新增追问决策能力（Agent 动态决策）。
"""
from agents.base import BaseAgent
from tools.question_tools import generate_questions
from tools.followup_tools import decide_followup


class InterviewerAgent(BaseAgent):
    name = "interviewer"

    def generate(self, resume: str, jd: str, total: int, type_ratio: dict) -> list:
        """生成主问题列表。"""
        return generate_questions(resume, jd, total, type_ratio, model_id=self.model_id)

    def decide_followup(self, question: str, answer: str, score: dict) -> dict:
        """L3-a: 根据回答质量决策是否追问 + 生成追问。
        返回 {"need_followup": bool, "reason": str, "followup_question": str|None}。
        任何异常都由工具层兜底为"不追问"。
        """
        return decide_followup(question, answer, score, model_id=self.model_id)
