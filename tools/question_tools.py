import json
from core.llm import get_model
from core.config import ROOT
from smolagents import ChatMessage, MessageRole


def _load_prompt(name: str) -> str:
    return (ROOT / "prompts" / name).read_text(encoding="utf-8")


def _ratio_to_distribution(total: int, type_ratio: dict) -> str:
    """把比例转成 '- 项目追问: 3题' 这样的文字"""
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
    """去掉可能的 markdown 代码块标记"""
    text = text.strip()
    if text.startswith("```"):
        # 取第一对 ``` 之间的内容
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text
        if text.lstrip().startswith("json"):
            text = text.lstrip()[4:]
    return text.strip()


def generate_questions(resume: str, jd: str, total: int, type_ratio: dict) -> list:
    """根据简历和JD生成面试题，返回 [{'type','question','difficulty'}, ...]"""
    prompt = _load_prompt("interviewer.txt").format(
        resume=resume,
        jd=jd,
        n=total,
        type_distribution=_ratio_to_distribution(total, type_ratio),
    )
    model = get_model()
    messages = [ChatMessage(role=MessageRole.USER, content=prompt)]
    response = model.generate(messages)
    text = _extract_json(response.content)

    try:
        questions = json.loads(text)
    except json.JSONDecodeError:
        raise ValueError(f"出题结果解析失败，模型原始返回:\n{text}")
    return questions
