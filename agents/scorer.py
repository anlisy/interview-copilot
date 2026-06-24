"""评分 Agent：负责打分。与面试官物理隔离 —— 不让出题者自己评估自己。"""
from agents.base import BaseAgent
from tools.score_tools import score_answer


class ScorerAgent(BaseAgent):
    name = "scorer"

    def score(self, q_type: str, question: str, answer: str):
        """对单题回答打分，返回 Score。"""
        return score_answer(q_type, question, answer)
