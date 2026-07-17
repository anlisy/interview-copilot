"""评分 Agent：负责打分。与面试官物理隔离。
L2-c: 评分用快模型省成本。
"""
from agents.base import BaseAgent
from tools.score_tools import score_answer


class ScorerAgent(BaseAgent):
    name = "scorer"

    def score(self, q_type: str, question: str, answer: str):
        """对单题回答打分，返回 Score。L2-c: 传路由的 model_id。"""
        return score_answer(q_type, question, answer, model_id=self.model_id)
