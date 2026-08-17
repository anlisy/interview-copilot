"""答题助手测试（mock检索和LLM，不真调）"""
from unittest.mock import patch


def test_answer_with_relevant_kb():
    """检索到相关资料 → source=kb"""
    import tools.answer_tools as at
    with patch.object(at, "search_knowledge",
                     return_value=[{"similarity": 0.8, "document": "d",
                                    "metadata": {"question": "q"}}]), \
         patch.object(at, "_is_relevant", return_value=True), \
         patch.object(at, "generate_with_retry", return_value="参考答案"):
        r = at.answer_question("HashMap原理")
        assert r["source"] == "kb"


def test_answer_irrelevant_kb_falls_to_ai():
    """检索到内容但不相关 → source=ai"""
    import tools.answer_tools as at
    with patch.object(at, "search_knowledge",
                     return_value=[{"similarity": 0.5, "document": "d",
                                    "metadata": {"question": "q"}}]), \
         patch.object(at, "_is_relevant", return_value=False), \
         patch.object(at, "generate_with_retry", return_value="AI答案"):
        r = at.answer_question("K8s原理")
        assert r["source"] == "ai"


def test_answer_no_kb_is_ai():
    """检索为空 → source=ai"""
    import tools.answer_tools as at
    with patch.object(at, "search_knowledge", return_value=[]), \
         patch.object(at, "generate_with_retry", return_value="AI答案"):
        r = at.answer_question("冷门问题")
        assert r["source"] == "ai"
        assert r["ref_count"] == 0


def test_answer_generation_failure():
    """答案生成失败有兜底，不抛异常"""
    import tools.answer_tools as at
    with patch.object(at, "search_knowledge", return_value=[]), \
         patch.object(at, "generate_with_retry", side_effect=Exception("挂了")):
        r = at.answer_question("q")
        assert "失败" in r["answer"]
