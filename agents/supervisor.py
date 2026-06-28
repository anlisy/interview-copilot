"""Supervisor 调度层：状态机驱动 + 题型配额分配 + 协调三个子 Agent。

设计要点：
- Supervisor 不做具体的 LLM 任务，只负责"调度"：决定下一步谁工作。
- 每个子 Agent 独立上下文，Supervisor 通过显式传参在它们之间传递必要信息。
- 用状态机约束流转，防止乱跳状态。
"""
from core.state import InterviewState, can_transit
from agents.interviewer import InterviewerAgent
from agents.scorer import ScorerAgent
from agents.reviewer import ReviewerAgent


class Supervisor:
    def __init__(self):
        self.interviewer = InterviewerAgent()
        self.scorer = ScorerAgent()
        self.reviewer = ReviewerAgent()
        self.state = InterviewState.INIT

    def _transit(self, dst: InterviewState):
        """受控的状态流转，非法流转直接报错（防御性）。"""
        if not can_transit(self.state, dst):
            raise RuntimeError(f"非法状态流转: {self.state} -> {dst}")
        self.state = dst

    # ---------- 出题阶段 ----------
    def run_generate(self, resume, jd, total, type_ratio) -> list:
        self._transit(InterviewState.GENERATING)
        questions = self.interviewer.generate(resume, jd, total, type_ratio)
        self._transit(InterviewState.ASKING)
        return questions

    # ---------- 评分阶段 ----------
    def run_score(self, q_type, question, answer, is_last: bool):
        """对一题打分。is_last 决定流转到下一题还是进入复盘。"""
        self._transit(InterviewState.SCORING)
        score = self.scorer.score(q_type, question, answer)
        # 评分后：还有题 -> 回到 ASKING；最后一题 -> 准备复盘
        self._transit(InterviewState.REVIEWING if is_last else InterviewState.ASKING)
        return score

    # ---------- 复盘阶段 ----------
    def run_review(self, position, qa_list) -> str:
        # 复盘可能从 ASKING(没经过最后评分) 或 REVIEWING 进入，这里兼容
        if self.state == InterviewState.ASKING:
            self._transit(InterviewState.SCORING)
            self._transit(InterviewState.REVIEWING)
        report = self.reviewer.review(position, qa_list)
        self._transit(InterviewState.FINISHED)
        return report

    # ---------- 状态导出/恢复（用于 Redis 持久化）----------
    def dump_state(self) -> str:
        """导出当前状态为字符串（存入 Redis）。"""
        return self.state.value

    @classmethod
    def from_state(cls, state_value: str) -> "Supervisor":
        """从状态字符串恢复一个 Supervisor（Agent 重新创建，state 恢复）。"""
        sup = cls()
        sup.state = InterviewState(state_value)
        return sup
