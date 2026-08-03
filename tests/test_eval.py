"""预测命中率评估测试（mock检索，不真调）"""
from unittest.mock import patch
from tools.eval_tools import evaluate_prediction, HIT_THRESHOLD


def test_hit_when_similarity_above_threshold():
    """相似度>=阈值 → 命中"""
    def fake_search(q, category=None, top_k=1):
        return [{"document": "d", "metadata": {"question": "真实题"}, "similarity": 0.7}]
    with patch("tools.eval_tools.search_knowledge", side_effect=fake_search):
        r = evaluate_prediction([{"question": "预测题"}])
        assert r["hits"] == 1
        assert r["hit_rate"] == 1.0
        assert r["details"][0]["hit"] is True


def test_miss_when_similarity_below_threshold():
    """相似度<阈值 → 未命中"""
    def fake_search(q, category=None, top_k=1):
        return [{"document": "d", "metadata": {"question": "真实题"}, "similarity": 0.4}]
    with patch("tools.eval_tools.search_knowledge", side_effect=fake_search):
        r = evaluate_prediction([{"question": "预测题"}])
        assert r["hits"] == 0
        assert r["hit_rate"] == 0.0


def test_hit_rate_calculation():
    """命中率计算：2命中/4总 = 50%"""
    sims = [0.7, 0.6, 0.3, 0.2]
    calls = {"i": 0}
    def fake_search(q, category=None, top_k=1):
        s = sims[calls["i"]]
        calls["i"] += 1
        return [{"document": "d", "metadata": {"question": "t"}, "similarity": s}]
    with patch("tools.eval_tools.search_knowledge", side_effect=fake_search):
        r = evaluate_prediction([{"question": f"q{i}"} for i in range(4)])
        assert r["hits"] == 2
        assert r["hit_rate"] == 0.5


def test_search_failure_counts_as_miss():
    """检索失败 → 记未命中，不中断"""
    with patch("tools.eval_tools.search_knowledge", side_effect=Exception("挂了")):
        r = evaluate_prediction([{"question": "预测题"}])
        assert r["hits"] == 0
