import json
from difflib import SequenceMatcher
from core.llm import generate_with_retry
from core.config import ROOT


def _load_prompt(name: str) -> str:
    return (ROOT / "prompts" / name).read_text(encoding="utf-8")


def _ratio_to_distribution(total: int, type_ratio: dict) -> str:
    name_map = {
        "RESUME_PROJECT": "项目追问", "RESUME_INTERNSHIP": "实习追问",
        "JAVA_BASIC": "Java八股", "AI_BASIC": "AI应用八股",
        "CODING": "编程题", "BEHAVIOR": "行为问题",
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


def _safe_json_load(text: str):
    text = _extract_json(text)
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


# ---------- 兜底去重（万一规划阶段也撞车）----------
def _is_duplicate(q1: str, q2: str) -> bool:
    return SequenceMatcher(None, q1, q2).ratio() > 0.55


def _dedup(items: list, key: str) -> list:
    kept = []
    for it in items:
        text = it.get(key, "")
        if not text:
            continue
        if any(_is_duplicate(text, k.get(key, "")) for k in kept):
            continue
        kept.append(it)
    return kept


# ---------- 第一步：规划考察点 ----------
def _plan_topics(resume, jd, total, type_ratio, model_id=None) -> list:
    prompt = _load_prompt("topic_planner.txt").format(
        resume=resume, jd=jd, n=total,
        type_distribution=_ratio_to_distribution(total, type_ratio),
    )
    topics = _safe_json_load(generate_with_retry(prompt, model_id=model_id)) or []
    # 对考察点本身去重（按 topic 文本）
    topics = _dedup(topics, "topic")
    return topics[:total]


# ---------- 第二步：按考察点出题 ----------
def _write_questions(resume, topics, model_id=None) -> list:
    topics_str = "\n".join(
        f'- [{t.get("type")}] {t.get("topic")}' for t in topics
    )
    prompt = _load_prompt("question_writer.txt").format(
        resume=resume, topics=topics_str,
    )
    questions = _safe_json_load(generate_with_retry(prompt, model_id=model_id)) or []
    # 兜底：再去重一次（按 question 文本）
    questions = _dedup(questions, "question")
    return questions


# ---------- 主入口 ----------
def generate_questions(resume: str, jd: str, total: int, type_ratio: dict, model_id: str = None) -> list:
    # 第一步：规划
    topics = _plan_topics(resume, jd, total, type_ratio, model_id)
    if not topics:
        raise ValueError("出题失败：考察点规划阶段返回空")
    print(f"  📋 已规划 {len(topics)} 个考察点: "
          + " | ".join(t.get("topic", "?") for t in topics))

    # 第二步：出题
    questions = _write_questions(resume, topics, model_id)
    if not questions:
        raise ValueError("出题失败：出题阶段返回空")

    print(f"  ✅ 最终出题 {len(questions)} 道（去重后）")
    return questions[:total]
