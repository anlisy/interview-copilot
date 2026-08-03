"""面试官 Agent：出题 + 追问决策 + 简历诊断。
独立上下文，评估隔离。
L2-c: 出题用强模型。L3-a: 追问决策。L3-d: 简历诊断(亮点/风险/追问预判)。
"""
from agents.base import BaseAgent
from tools.question_tools import generate_questions
from tools.followup_tools import decide_followup
from tools.diagnose_tools import diagnose_resume


class InterviewerAgent(BaseAgent):
    name = "interviewer"

    def generate(self, resume: str, jd: str, total: int, type_ratio: dict) -> list:
        """生成主问题列表。"""
        return generate_questions(resume, jd, total, type_ratio, model_id=self.model_id)

    def decide_followup(self, question: str, answer: str, score: dict,
                        followup_count: int = 0) -> dict:
        """L3-a: 决策是否追问 + 生成追问。L3-d: 传追问轮次实现5层递进。"""
        return decide_followup(question, answer, score,
                              model_id=self.model_id, followup_count=followup_count)

    def diagnose(self, resume: str, jd: str) -> dict:
        """L3-d: 面试官视角诊断简历，返回亮点/风险/追问预判/建议。"""
        return diagnose_resume(resume, jd, model_id=self.model_id)
