"""面试题预测：出题 + 预判追问 + 覆盖率/命中率报告。
用于生成"面试可能被问的问题清单"，不需要用户答题。
"""
import json
from core.config import ROOT
from core.llm import generate_with_retry
from tools.question_tools import generate_questions, generate_questions_by_counts
from tools.eval_tools import evaluate_prediction


def _load_prompt(name: str) -> str:
    return (ROOT / "prompts" / name).read_text(encoding="utf-8")


def _predict_followups(question: str, model_id: str = None, retry: int = 1) -> list:
    """为一道题预判追问链（不看回答）。失败重试一次，再失败返回空。"""
    for attempt in range(retry + 1):
        try:
            prompt = _load_prompt("followup_predict.txt").format(question=question)
            text = generate_with_retry(prompt, model_id=model_id).strip()
            # 去 markdown 包裹
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
            if text.lstrip().startswith("json"):
                text = text.lstrip()[4:]
            # 提取 [...] 子串
            start, end = text.find("["), text.rfind("]")
            if start != -1 and end != -1:
                text = text[start:end+1]
            result = json.loads(text.strip())
            if isinstance(result, list) and result:
                return [str(x) for x in result]
        except Exception:
            if attempt < retry:
                continue
    print(f"  ⚠️ 预判追问失败，该题无追问")
    return []


def _type_ratio_from_counts(type_counts: dict) -> tuple:
    """把 {题型:数量} 转成 generate_questions 需要的 (total, type_ratio)。"""
    name_to_key = {
        "项目追问": "RESUME_PROJECT", "实习追问": "RESUME_INTERNSHIP",
        "Java八股": "JAVA_BASIC", "AI应用八股": "AI_BASIC",
        "编程题": "CODING", "行为问题": "BEHAVIOR",
    }
    total = sum(type_counts.values())
    if total == 0:
        return 0, {}
    ratio = {}
    for name, cnt in type_counts.items():
        key = name_to_key.get(name)
        if key and cnt > 0:
            ratio[key] = round(cnt / total * 100)
    return total, ratio


def predict_interview(resume: str, jd: str, type_counts: dict,
                     with_coverage: bool = False,
                     with_hit_rate: bool = False,
                     on_questions=None, on_item=None) -> dict:
    """生成面试预测题 + 预判追问 + 可选报告。

    流式回调（可选，用于边生成边展示，避免干等）：
      on_questions(questions): 出题完成后立刻回调（先让用户看到题目）
      on_item(index, total, item): 每道题追问生成后立刻回调（逐题展示）
    不传回调则行为不变（一次性返回）。

    type_counts: {"实习追问": 3, "项目追问": 3, ...}
    """
    total = sum(type_counts.values())
    if total == 0:
        raise ValueError("题目总数为0")

    # 出题：精确按题型数量（绕过百分比转换 + 语义去重）
    questions = generate_questions_by_counts(resume, jd, type_counts)
    if on_questions:
        on_questions(questions)   # 流式：出题完立刻展示

    # 每题预判追问（每道算完立刻回调展示）
    items = []
    n = len(questions)
    for idx, q in enumerate(questions):
        followups = _predict_followups(q.get("question", ""))
        item = {
            "type": q.get("type"),
            "question": q.get("question"),
            "difficulty": q.get("difficulty", ""),
            "followups": followups,
        }
        items.append(item)
        if on_item:
            on_item(idx + 1, n, item)   # 流式：每题追问完立刻展示

    result = {"questions": items, "total": len(items)}

    # 可选：命中率报告
    if with_hit_rate:
        eval_r = evaluate_prediction([{"question": i["question"]} for i in items])
        result["hit_rate"] = eval_r

    # 可选：覆盖率报告（简历技术点覆盖度）
    if with_coverage:
        result["coverage"] = _analyze_coverage(resume, items)

    return result


def _analyze_coverage(resume: str, items: list) -> dict:
    """分析出题覆盖了简历多少技术点（用LLM抽取技术点+判断覆盖）。"""
    try:
        questions_text = "\n".join(f"- {i['question']}" for i in items)
        prompt = f"""分析出题对简历技术点的覆盖情况。

【简历】
{resume}

【已出的题】
{questions_text}

【任务】
1. 从简历提取主要技术点/经历（5-10个）
2. 判断每个是否被上面的题覆盖到
严格输出JSON：
{{"all_points": ["技术点1", ...], "covered": ["被覆盖的点", ...], "uncovered": ["未覆盖的点", ...]}}"""
        text = generate_with_retry(prompt).strip()
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1:
            text = text[start:end+1]
        r = json.loads(text)
        total_pts = len(r.get("all_points", []))
        covered = len(r.get("covered", []))
        return {
            "all_points": r.get("all_points", []),
            "covered": r.get("covered", []),
            "uncovered": r.get("uncovered", []),
            "coverage_rate": round(covered / total_pts, 2) if total_pts else 0,
        }
    except Exception as e:
        print(f"  ⚠️ 覆盖率分析失败({type(e).__name__})")
        return {}
