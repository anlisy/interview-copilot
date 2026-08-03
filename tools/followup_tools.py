"""追问决策工具：判断是否要追问 + 生成追问。

L3-a 核心：Agent 根据回答质量做决策，识别可挖掘点。
包含三层兜底，确保任何异常都优雅退化为"不追问"。
"""
import json
from core.llm import generate_with_retry
from core.config import ROOT


def _load_prompt(name: str) -> str:
    return (ROOT / "prompts" / name).read_text(encoding="utf-8")


def decide_followup(
    question: str,
    answer: str,
    score: dict,
    model_id: str = None,
    followup_count: int = 0
) -> dict:
    """
    判断是否要追问 + 生成追问问题。
    
    Args:
        question: 原问题
        answer: 用户回答
        score: 评分结果 (Score dataclass 转的 dict)
        model_id: 模型ID（路由用）
    
    Returns:
        {
            "need_followup": bool,
            "reason": str,
            "followup_question": str or None
        }
    
    兜底保证：任何异常返回 {"need_followup": False, ...}
    """
    # 第三层兜底：调用失败
    try:
        prompt = _load_prompt("followup_decision.txt").format(
            question=question,
            answer=answer or "(未作答)",
            score_total=score.get("total", 0),
            accuracy=score.get("accuracy", 0),
            completeness=score.get("completeness", 0),
            depth=score.get("depth", 0),
            clarity=score.get("clarity", 0),
            comment=score.get("comment", ""),
            followup_round=followup_count + 1
        )
        
        text = generate_with_retry(prompt, model_id=model_id).strip()
        
        # 去除可能的 markdown 代码块
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
            if text.lstrip().startswith("json"):
                text = text.lstrip()[4:]
        
        # 第一层兜底：解析失败
        result = json.loads(text.strip())
        
        # 校验必须字段
        if "need_followup" not in result:
            print("⚠️ 追问决策缺 need_followup 字段，默认不追问")
            return {"need_followup": False, "reason": "解析失败", "followup_question": None}
        
        need = bool(result.get("need_followup", False))

        # 硬门槛兜底：分数太高强制不追问（防止模型无脑追问）
        total = score.get("total", 0)
        if total >= 4.5:
            need = False
            print(f"  ⛔ 硬门槛: 总分{total}>=4.5，强制不追问")
        # 硬门槛兜底：回答太空洞（准确性极低）也不追问（追问没意义）
        if score.get("accuracy", 0) <= 1:
            need = False
            print(f"  ⛔ 硬门槛: 回答太空洞，不追问")

        return {
            "need_followup": need,
            "reason": result.get("reason", ""),
            "followup_question": result.get("followup_question") if need else None
        }
    
    except Exception as e:
        # 第三层兜底生效
        print(f"⚠️ 追问决策调用失败({type(e).__name__}): {str(e)[:50]}，降级为不追问")
        return {"need_followup": False, "reason": "调用失败", "followup_question": None}
