import json
from core.llm import generate_with_retry
from core.config import ROOT
from core.models import Score


def _load_prompt(name: str) -> str:
    return (ROOT / "prompts" / name).read_text(encoding="utf-8")


def _extract_json(text: str) -> str:
    text = (text or "").strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text
        if text.lstrip().startswith("json"):
            text = text.lstrip()[4:]
    return text.strip()


def score_answer(q_type: str, question: str, answer: str) -> Score:
    """对一道题的回答打分，返回 Score 对象"""
    if not answer or not answer.strip():
        return Score(0, 0, 0, 0, 0.0, "未作答。")

    prompt = _load_prompt("scorer.txt").format(
        q_type=q_type, question=question, answer=answer
    )
    text = _extract_json(generate_with_retry(prompt))

    try:
        d = json.loads(text)
    except json.JSONDecodeError:
        raise ValueError(f"打分结果解析失败，模型原始返回:\n{text}")

    return Score(
        accuracy=int(d.get("accuracy", 0)),
        completeness=int(d.get("completeness", 0)),
        depth=int(d.get("depth", 0)),
        clarity=int(d.get("clarity", 0)),
        total=float(d.get("total", 0)),
        comment=d.get("comment", ""),
    )
