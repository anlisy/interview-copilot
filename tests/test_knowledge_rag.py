"""知识库 RAG 测试：解析、检索、题型映射（mock embedding/LLM，不真调）"""
from pathlib import Path
from unittest.mock import patch
from tools.knowledge_tools import parse_markdown, _clean


def test_clean_removes_escapes_and_images():
    """清理：去转义符 + 去图片链接"""
    raw = r"扩容为1\.5倍 ![Image](http://xxx) 内存\<\>权衡"
    cleaned = _clean(raw)
    assert "\\" not in cleaned
    assert "![Image]" not in cleaned
    assert "1.5倍" in cleaned


def test_parse_markdown_splits_by_h4(tmp_path):
    """解析：按 #### 切分成问答块"""
    md = tmp_path / "test.md"
    md.write_text(
        "# 标题\n### 分类A\n#### 问题1\n答案1内容\n#### 问题2\n答案2内容\n",
        encoding="utf-8"
    )
    blocks = parse_markdown(md)
    assert len(blocks) == 2
    assert blocks[0]["question"] == "问题1"
    assert blocks[0]["answer"] == "答案1内容"
    assert blocks[0]["topic"] == "分类A"


def test_type_to_category_mapping():
    """题型→分类映射：八股→八股，项目→None"""
    from tools.question_tools import _TYPE_TO_CATEGORY
    assert _TYPE_TO_CATEGORY["Java八股"] == "八股"
    assert _TYPE_TO_CATEGORY["项目追问"] is None


def test_retrieve_reference_project_no_search():
    """项目类考点不检索，直接返回空"""
    from tools.question_tools import _retrieve_reference
    assert _retrieve_reference("项目追问", "任意") == ""


def test_retrieve_reference_search_failure_degrades():
    """检索报错时降级为空，不影响出题"""
    from tools.question_tools import _retrieve_reference
    with patch("tools.question_tools.search_knowledge", side_effect=Exception("库挂了")):
        assert _retrieve_reference("Java八股", "HashMap") == ""
