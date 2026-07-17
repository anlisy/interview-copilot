"""Supervisor 追问调度测试：验证硬上限兜底 + 状态流转"""
import pytest
from unittest.mock import patch
from agents.supervisor import Supervisor
from core.state import InterviewState


def test_followup_hard_limit():
    """硬上限：followup_count >= max_followup 强制不追问"""
    sup = Supervisor()
    sup.state = InterviewState.SCORING
    # 即使 Agent 想追问，达到上限也不追
    need, fq, reason = sup.decide_followup(
        "q", "a", {"total": 3.0, "accuracy": 4}, followup_count=2, max_followup=2
    )
    assert need is False
    assert "上限" in reason


def test_go_followup_transition():
    """go_followup: SCORING → FOLLOWUP"""
    sup = Supervisor()
    sup.state = InterviewState.SCORING
    sup.go_followup()
    assert sup.state == InterviewState.FOLLOWUP


def test_go_next_transition():
    """go_next_or_finish: SCORING → ASKING（非最后题）"""
    sup = Supervisor()
    sup.state = InterviewState.SCORING
    sup.go_next_or_finish(is_last=False)
    assert sup.state == InterviewState.ASKING
