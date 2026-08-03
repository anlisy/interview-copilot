"""Eval 历史记录：每次评估存一条，用于展示预测能力的进化趋势。
用 JSON 文件追加存储，简单够用。
"""
import json
from datetime import datetime
from pathlib import Path
from core.config import ROOT

HISTORY_FILE = ROOT / "data" / "eval_history.json"


def _knowledge_count() -> int:
    """当前知识库条数（关联'越用越准'的证据）。"""
    try:
        from tools.knowledge_tools import _get_collection
        return _get_collection().count()
    except Exception:
        return 0


def record_eval(eval_result: dict, position: str = "", note: str = ""):
    """记录一次评估结果。eval_result 是 evaluate_prediction 的返回。"""
    record = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "hit_rate": eval_result.get("hit_rate", 0),
        "hits": eval_result.get("hits", 0),
        "total": eval_result.get("total", 0),
        "threshold": eval_result.get("threshold", 0),
        "knowledge_count": _knowledge_count(),
        "position": position,
        "note": note,
    }
    history = load_history()
    history.append(record)
    HISTORY_FILE.write_text(
        json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    return record


def load_history() -> list:
    """读取所有历史记录。"""
    if not HISTORY_FILE.exists():
        return []
    try:
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def print_trend():
    """打印进化趋势（命中率随知识库规模的变化）。"""
    history = load_history()
    if not history:
        print("暂无评估历史")
        return
    print("=== 预测命中率进化趋势 ===")
    print(f"{'时间':<20} {'知识库':<8} {'命中率':<8} {'备注'}")
    for h in history:
        print(f"{h['timestamp']:<20} {h['knowledge_count']:<8} "
              f"{h['hit_rate']*100:.0f}%{'':<5} {h.get('note', '')}")
