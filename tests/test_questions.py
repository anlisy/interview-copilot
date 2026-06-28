"""测试出题工具的去重逻辑（不依赖真实 LLM，纯本地逻辑）"""
from tools.question_tools import _is_duplicate, _dedup


def test_duplicate_same_topic():
    """两题高度相似应判定为重复"""
    q1 = "请介绍rerank重排序的原理"
    q2 = "请介绍rerank重排序的原理是什么"
    assert _is_duplicate(q1, q2) is True


def test_not_duplicate_different_topic():
    """两题问不同技术点应判定为不重复"""
    q1 = "请介绍rerank的原理"
    q2 = "Redis的持久化机制有哪些"
    assert _is_duplicate(q1, q2) is False


def test_dedup_removes_duplicates():
    """去重函数应剔除重复题，保留第一个"""
    questions = [
        {"type": "项目追问", "question": "你的rerank是怎么集成的？请详细说明集成方案"},
        {"type": "AI应用八股", "question": "你的rerank是怎么集成的？请详细说明集成方案啊"},
        {"type": "Java八股", "question": "Redis分布式锁怎么实现"},
    ]
    result = _dedup(questions, "question")
    assert len(result) == 2
    assert result[0]["question"].startswith("你的rerank")
    assert result[1]["question"] == "Redis分布式锁怎么实现"


def test_dedup_skips_empty():
    """去重应跳过空题目"""
    questions = [
        {"type": "项目追问", "question": ""},
        {"type": "Java八股", "question": "Redis分布式锁怎么实现"},
    ]
    result = _dedup(questions, "question")
    assert len(result) == 1
