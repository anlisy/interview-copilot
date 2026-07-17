"""追问功能测试：验证追问决策 + 三层兜底（mock，不调真实 LLM）"""
import pytest
from unittest.mock import patch
from tools.followup_tools import decide_followup


def test_high_score_no_followup():
    """硬门槛：总分>=4.5 强制不追问（不管LLM说什么）"""
    with patch("tools.followup_tools.generate_with_retry",
               return_value='{"need_followup": true, "reason": "x", "followup_question": "y"}'):
        r = decide_followup("q", "完整回答",
                            {"total": 4.8, "accuracy": 5, "completeness": 5,
                             "depth": 5, "clarity": 4, "comment": ""})
        assert r["need_followup"] is False   # 被硬门槛拦


def test_empty_answer_no_followup():
    """硬门槛：回答太空洞（accuracy<=1）不追问"""
    with patch("tools.followup_tools.generate_with_retry",
               return_value='{"need_followup": true, "reason": "x", "followup_question": "y"}'):
        r = decide_followup("q", "空洞",
                            {"total": 1.0, "accuracy": 1, "completeness": 1,
                             "depth": 1, "clarity": 1, "comment": ""})
        assert r["need_followup"] is False


def test_shallow_answer_triggers_followup():
    """浅回答（分数中等）+ LLM 说要追问 → 追问"""
    with patch("tools.followup_tools.generate_with_retry",
               return_value='{"need_followup": true, "reason": "太简洁", "followup_question": "具体呢?"}'):
        r = decide_followup("q", "用了向量检索",
                            {"total": 3.0, "accuracy": 4, "completeness": 2,
                             "depth": 3, "clarity": 3, "comment": ""})
        assert r["need_followup"] is True
        assert r["followup_question"] == "具体呢?"


def test_json_parse_failure_no_followup():
    """兜底：LLM 返回非JSON → 默认不追问"""
    with patch("tools.followup_tools.generate_with_retry",
               return_value='这不是JSON乱七八糟'):
        r = decide_followup("q", "a",
                            {"total": 3.0, "accuracy": 3, "completeness": 3,
                             "depth": 3, "clarity": 3, "comment": ""})
        assert r["need_followup"] is False


def test_llm_exception_no_followup():
    """兜底：LLM 调用抛异常 → 默认不追问"""
    with patch("tools.followup_tools.generate_with_retry",
               side_effect=Exception("网络错误")):
        r = decide_followup("q", "a",
                            {"total": 3.0, "accuracy": 3, "completeness": 3,
                             "depth": 3, "clarity": 3, "comment": ""})
        assert r["need_followup"] is False
