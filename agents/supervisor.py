"""Supervisor 调度层：状态机驱动 + 协调子 Agent。

L3-a: 新增追问调度。核心方法入口无关（纯数据参数），
前端和 CLI 都能调用同一套逻辑。
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
        if not can_transit(self.state, dst):
            raise RuntimeError(f"非法状态流转: {self.state} -> {dst}")
        self.state = dst

    # ---------- 出题阶段 ----------
    def run_generate(self, resume, jd, total, type_ratio) -> list:
        self._transit(InterviewState.GENERATING)
        questions = self.interviewer.generate(resume, jd, total, type_ratio)
        self._transit(InterviewState.ASKING)
        return questions

    # ---------- 评分阶段（旧版，不追问，保持向后兼容）----------
    def run_score(self, q_type, question, answer, is_last: bool):
        """对一题打分并直接流转（L2 行为，不追问）。
        保留此方法保证旧接口/旧测试向后兼容。"""
        self._transit(InterviewState.SCORING)
        score = self.scorer.score(q_type, question, answer)
        self._transit(InterviewState.REVIEWING if is_last else InterviewState.ASKING)
        return score

    # ---------- 评分 + 追问决策（L3-a 新流程）----------
    def run_score_only(self, q_type, question, answer):
        """只评分，评完停在 SCORING 状态（不流转），把去向交给追问逻辑。
        用于支持追问的新流程。可从 ASKING(主问题) 或 FOLLOWUP(追问) 进入。"""
        self._transit(InterviewState.SCORING)
        return self.scorer.score(q_type, question, answer)

    def decide_followup(self, question, answer, score, followup_count, max_followup):
        """评分后决策是否追问（当前状态应为 SCORING）。
        返回 (need_followup, followup_question, reason)。

        兜底：
        - 硬上限：followup_count >= max_followup 强制不追问
        - 分数门槛 + 调用失败：由 decide_followup 工具层兜底
        """
        if followup_count >= max_followup:
            return False, None, f"已达追问上限({max_followup})"
        decision = self.interviewer.decide_followup(question, answer, score)
        return (decision["need_followup"],
                decision.get("followup_question"),
                decision.get("reason", ""))

    def go_followup(self):
        """确认追问：SCORING → FOLLOWUP。"""
        self._transit(InterviewState.FOLLOWUP)

    def go_next_or_finish(self, is_last: bool):
        """不追问：SCORING → ASKING(下一题) 或 REVIEWING(结束)。"""
        self._transit(InterviewState.REVIEWING if is_last else InterviewState.ASKING)

    # ---------- 复盘阶段 ----------
    def run_review(self, position, qa_list) -> str:
        if self.state == InterviewState.ASKING:
            self._transit(InterviewState.SCORING)
            self._transit(InterviewState.REVIEWING)
        report = self.reviewer.review(position, qa_list)
        self._transit(InterviewState.FINISHED)
        return report

    # ---------- 状态导出/恢复（Redis 持久化）----------
    def dump_state(self) -> str:
        return self.state.value

    @classmethod
    def from_state(cls, state_value: str) -> "Supervisor":
        sup = cls()
        sup.state = InterviewState(state_value)
        return sup
