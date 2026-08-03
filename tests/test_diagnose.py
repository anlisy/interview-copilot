"""简历诊断测试（mock LLM，不真调）"""
from unittest.mock import patch
from tools.diagnose_tools import diagnose_resume


def test_diagnose_parses_json():
    fake = '{"highlights":[{"point":"RAG项目","why":"核心技能","likely_followup":"怎么优化召回"}],"risks":[{"point":"缺量化","challenge":"数据从哪来"}],"suggestions":["补充数据"]}'
    with patch("tools.diagnose_tools.generate_with_retry", return_value=fake):
        r = diagnose_resume("简历", "JD")
        assert len(r["highlights"]) == 1
        assert r["highlights"][0]["likely_followup"] == "怎么优化召回"
        assert r["suggestions"] == ["补充数据"]


def test_diagnose_parse_failure_returns_empty():
    with patch("tools.diagnose_tools.generate_with_retry", return_value="不是JSON"):
        r = diagnose_resume("简历", "JD")
        assert r == {"highlights": [], "risks": [], "suggestions": []}


def test_diagnose_exception_returns_empty():
    with patch("tools.diagnose_tools.generate_with_retry", side_effect=Exception("挂了")):
        r = diagnose_resume("简历", "JD")
        assert r["highlights"] == []
