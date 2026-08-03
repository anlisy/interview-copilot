"""Eval 历史记录测试（用临时文件，不污染真实历史）"""
import json
from unittest.mock import patch


def test_record_and_load(tmp_path, monkeypatch):
    """记录一条 + 读取"""
    import tools.eval_history as eh
    fake_file = tmp_path / "hist.json"
    monkeypatch.setattr(eh, "HISTORY_FILE", fake_file)
    monkeypatch.setattr(eh, "_knowledge_count", lambda: 300)

    eh.record_eval({"hit_rate": 0.6, "hits": 3, "total": 5, "threshold": 0.55},
                   position="AI岗", note="test")
    history = eh.load_history()
    assert len(history) == 1
    assert history[0]["hit_rate"] == 0.6
    assert history[0]["knowledge_count"] == 300
    assert history[0]["note"] == "test"


def test_append_multiple(tmp_path, monkeypatch):
    """多次记录追加"""
    import tools.eval_history as eh
    fake_file = tmp_path / "hist.json"
    monkeypatch.setattr(eh, "HISTORY_FILE", fake_file)
    monkeypatch.setattr(eh, "_knowledge_count", lambda: 300)

    eh.record_eval({"hit_rate": 0.6, "hits": 3, "total": 5}, note="第1次")
    eh.record_eval({"hit_rate": 0.75, "hits": 3, "total": 4}, note="第2次")
    assert len(eh.load_history()) == 2


def test_load_empty_when_no_file(tmp_path, monkeypatch):
    """无历史文件返回空列表"""
    import tools.eval_history as eh
    monkeypatch.setattr(eh, "HISTORY_FILE", tmp_path / "nonexist.json")
    assert eh.load_history() == []
