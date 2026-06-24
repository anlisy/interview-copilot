import json
from core.llm import generate_with_retry
from core.config import ROOT


def _load_prompt(name: str) -> str:
    return (ROOT / "prompts" / name).read_text(encoding="utf-8")


def _ratio_to_distribution(total: int, type_ratio: dict) -> str:
    name_map = {
        "RESUME_PROJECT": "项目追问",
        "RESUME_INTERNSHIP": "实习追问",
        "JAVA_BASIC": "Java八股",
        "AI_BASIC": "AI应用八股",
        "CODING": "编程题",
        "BEHAVIOR": "行为问题",
    }
    lines = []
    for key, pct in type_ratio.items():
        n = round(total * pct / 100)
        if n > 0:
            lines.append(f"- {name_map.get(key, key)}: {n}题")
    return "\n".join(lines)


def _extract_json(text: str) -> str:
    text = (text or "").strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text
        if text.lstrip().startswith("json"):
            text = text.lstrip()[4:]
    return text.strip()


def generate_questions(resume: str, jd: str, total: int, type_ratio: dict) -> list:
    prompt = _load_prompt("interviewer.txt").format(
        resume=resume, jd=jd, n=total,
        type_distribution=_ratio_to_distribution(total, type_ratio),
    )
    text = _extract_json(generate_with_retry(prompt))

    if not text:
        raise ValueError("出题失败：模型返回空内容")

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        raise ValueError(f"出题结果解析失败，模型原始返回:\n{text}")
