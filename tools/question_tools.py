import json
from difflib import SequenceMatcher
from core.llm import generate_with_retry
from core.models import QType

_VALID_TYPES = {t.value for t in QType}  # 合法题型枚举
from tools.knowledge_tools import search_knowledge
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
def _semantic_dedup(questions: list, threshold: float = 0.88) -> list:
    """语义去重：用 embedding 相似度去掉意思雷同的题（字面去重的补充）。
    失败则降级为只做字面去重，不中断。"""
    if len(questions) <= 1:
        return questions
    try:
        from core.embedding import embed_texts
        texts = [q.get("question", "") for q in questions]
        embs = embed_texts(texts)
        kept, kept_embs = [], []
        import math
        def cos(a, b):
            dot = sum(x*y for x, y in zip(a, b))
            na = math.sqrt(sum(x*x for x in a))
            nb = math.sqrt(sum(x*x for x in b))
            return dot/(na*nb) if na and nb else 0
        for q, e in zip(questions, embs):
            if any(cos(e, ke) > threshold for ke in kept_embs):
                print(f"  🔁 语义去重丢弃: {q.get('question','')[:25]}")
                continue
            kept.append(q)
            kept_embs.append(e)
        return kept
    except Exception as e:
        print(f"  ⚠️ 语义去重失败({type(e).__name__})，降级字面去重")
        return _dedup(questions, "question")


def _is_duplicate(q1: str, q2: str) -> bool:
    return SequenceMatcher(None, q1, q2).ratio() > 0.55


def _filter_valid_types(questions: list) -> list:
    """harness: 过滤 type 不在合法枚举里的题（约束结构性错误）。"""
    valid = []
    for q in questions:
        if q.get("type") in _VALID_TYPES:
            valid.append(q)
        else:
            print(f"  ⚠️ 丢弃非法题型: {q.get('type')} - {q.get('question','')[:20]}")
    return valid


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
# 题型 → 知识库分类的映射（None 表示不检索，贴合简历的题不用检索）
_TYPE_TO_CATEGORY = {
    "Java八股": "八股",
    "AI应用八股": "八股",
    "编程题": "算法",
    "实习追问": "实习",
    "项目追问": "项目",
    "行为问题": None,
}


def _retrieve_reference(topic_type, topic_text, eval_mode=False) -> str:
    """检索知识库返回参考题。
    - 八股/算法/实习类：检索对应分类知识
    - 所有类型：额外检索面经（真实被问过的题）
    RAG 是增强项：检索空或报错都降级，不影响出题。"""
    refs = []
    try:
        category = _TYPE_TO_CATEGORY.get(topic_type)
        if category:
            refs += search_knowledge(topic_text, category=category, top_k=2)
        # 所有题型都检索面经（eval模式除外，避免看着答案出题作弊）
        if not eval_mode:
            refs += search_knowledge(topic_text, category="面经", top_k=1)
    except Exception as e:
        print(f"  ⚠️ 知识库检索失败({type(e).__name__})，降级为无参考")
        return ""
    if not refs:
        return ""
    lines = [f"  · {r['metadata'].get('question', '')}: {r['document'][:120]}"
             for r in refs]
    return "\n".join(lines)


def _write_questions(resume, topics, model_id=None, eval_mode=False) -> list:
    # 为每个考点拼上检索到的参考题（八股/算法类才检索）
    topic_lines = []
    for t in topics:
        line = f'- [{t.get("type")}] {t.get("topic")}'
        ref = _retrieve_reference(t.get("type"), t.get("topic"), eval_mode=eval_mode)
        if ref:
            line += f'\n  参考真实题库（可基于此出题或改编）：\n{ref}'
        topic_lines.append(line)
    topics_str = "\n".join(topic_lines)

    prompt = _load_prompt("question_writer.txt").format(
        resume=resume, topics=topics_str,
    )
    questions = _safe_json_load(generate_with_retry(prompt, model_id=model_id)) or []
    questions = _dedup(questions, "question")
    questions = _filter_valid_types(questions)   # harness: 题型合法性校验
    return questions


# ---------- 主入口 ----------
def generate_questions(resume: str, jd: str, total: int, type_ratio: dict, model_id: str = None, eval_mode: bool = False) -> list:
    # 第一步：规划
    topics = _plan_topics(resume, jd, total, type_ratio, model_id)
    if not topics:
        raise ValueError("出题失败：考察点规划阶段返回空")
    print(f"  📋 已规划 {len(topics)} 个考察点: "
          + " | ".join(t.get("topic", "?") for t in topics))

    # 第二步：出题
    questions = _write_questions(resume, topics, model_id, eval_mode=eval_mode)
    if not questions:
        raise ValueError("出题失败：出题阶段返回空")

    print(f"  ✅ 最终出题 {len(questions)} 道（去重后）")
    return questions[:total]


# ---------- predict 专用：精确题型数量出题（绕过百分比转换）----------
def _plan_topics_exact(resume, jd, count_distribution: str, total: int, model_id=None) -> list:
    """按精确题型数量分布规划考点。count_distribution 如 '- 实习追问: 10题\n- 项目追问: 10题'"""
    prompt = _load_prompt("topic_planner.txt").format(
        resume=resume, jd=jd, n=total, type_distribution=count_distribution,
    )
    topics = _safe_json_load(generate_with_retry(prompt, model_id=model_id)) or []
    topics = _dedup(topics, "topic")
    return topics[:total]


def generate_questions_by_counts(resume: str, jd: str, type_counts: dict, model_id: str = None) -> list:
    """predict 专用：按精确题型数量出题。
    type_counts 如 {'实习追问': 10, '项目追问': 10, 'Java八股': 1}。
    """
    total = sum(type_counts.values())
    if total == 0:
        return []
    # 直接构造精确数量分布（不转百分比）
    count_distribution = "\n".join(
        f"- {t}: {n}题" for t, n in type_counts.items() if n > 0
    )
    topics = _plan_topics_exact(resume, jd, count_distribution, total, model_id)
    if not topics:
        raise ValueError("出题失败：考察点规划返回空")
    print(f"  📋 已规划 {len(topics)} 个考察点")
    questions = _write_questions(resume, topics, model_id)
    questions = _semantic_dedup(questions)   # 语义去重
    print(f"  ✅ 最终出题 {len(questions)} 道（语义去重后）")
    return questions[:total]
