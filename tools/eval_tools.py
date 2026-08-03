"""预测命中率评估：用真实面经当 ground truth，评估系统预测题的命中率。

核心思想：系统预测的题，能在真实面经库里找到语义相似的 → 命中。
命中率 = 模拟真实面试的量化指标。

阈值 0.55 来自分数标定实验（相关题~0.6，无关题~0.3，边界~0.5）。
"""
from tools.knowledge_tools import search_knowledge
from tools.eval_history import record_eval

HIT_THRESHOLD = 0.55   # 命中阈值（数据标定得出）


def evaluate_prediction(predicted_questions: list, threshold: float = HIT_THRESHOLD) -> dict:
    """评估一批预测题对真实面经的命中率。

    Args:
        predicted_questions: [{"type":..., "question":...}, ...] 系统预测的题
        threshold: 命中阈值

    Returns:
        {
          "hit_rate": 0.75,
          "total": 4, "hits": 3,
          "threshold": 0.55,
          "details": [
            {"question": 预测题, "hit": True,
             "matched": 最相似真实面经, "similarity": 0.62},
            ...
          ]
        }
    兜底：面经库检索失败的题记为未命中，不中断整体评估。
    """
    details = []
    hits = 0
    for q in predicted_questions:
        question = q.get("question", "") if isinstance(q, dict) else str(q)
        try:
            refs = search_knowledge(question, category="面经", top_k=1)
        except Exception as e:
            print(f"  ⚠️ 评估检索失败({type(e).__name__})，该题记未命中")
            refs = []

        if refs:
            sim = refs[0]["similarity"]
            matched = refs[0]["metadata"].get("question", "")
        else:
            sim = 0.0
            matched = ""

        hit = sim >= threshold
        if hit:
            hits += 1
        details.append({
            "question": question,
            "hit": hit,
            "matched": matched,
            "similarity": sim,
        })

    total = len(predicted_questions)
    return {
        "hit_rate": round(hits / total, 4) if total else 0.0,
        "total": total,
        "hits": hits,
        "threshold": threshold,
        "details": details,
    }


def run_prediction_eval(resume: str, jd: str, total: int = 8, note: str = "") -> dict:
    """完整的预测命中率评估流程：
    1. eval模式出题（不看面经，纯预测）
    2. 用面经库评估命中率
    这是可量化的"模拟真实面试"能力评估。
    """
    from tools.question_tools import generate_questions
    # eval 模式出题：不检索面经，纯靠简历+JD预测
    predicted = generate_questions(
        resume, jd, total,
        type_ratio={"RESUME_PROJECT": 25, "RESUME_INTERNSHIP": 20,
                    "JAVA_BASIC": 25, "AI_BASIC": 20, "BEHAVIOR": 10},
        eval_mode=True,
    )
    result = evaluate_prediction(predicted)
    result["predicted_questions"] = predicted
    # 记录到 Eval 历史（用于展示进化趋势）
    try:
        record_eval(result, position=jd, note=note)
    except Exception as e:
        print(f"  ⚠️ Eval历史记录失败: {e}")
    return result
