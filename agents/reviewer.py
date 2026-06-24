"""复盘 Agent：负责综合所有问答与打分，生成复盘报告。"""
from agents.base import BaseAgent
from tools.review_tools import generate_review


class ReviewerAgent(BaseAgent):
    name = "reviewer"

    def review(self, position: str, qa_list: list) -> str:
        """生成整场复盘报告（Markdown）。"""
        return generate_review(position, qa_list)
