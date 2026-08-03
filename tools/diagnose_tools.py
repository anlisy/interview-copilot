"""简历诊断：面试官视角分析简历的亮点/风险/追问预判/建议。"""
import json
from core.llm import generate_with_retry
from core.config import ROOT


def _load_prompt(name: str) -> str:
    return (ROOT / "prompts" / name).read_text(encoding="utf-8")


def diagnose_resume(resume: str, jd: str, model_id: str = None) -> dict:
    """分析简历，返回 {highlights, risks, suggestions}。
    解析失败兜底为空结构，不中断流程。"""
    try:
        prompt = _load_prompt("resume_diagnose.txt").format(resume=resume, jd=jd)
        text = generate_with_retry(prompt, model_id=model_id).strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
            if text.lstrip().startswith("json"):
                text = text.lstrip()[4:]
        # harness: 健壮提取JSON（模型可能包裹解释文字）
        text = text.strip()
        if not text.startswith("{"):
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1:
                text = text[start:end+1]
        result = json.loads(text)
        return {
            "highlights": result.get("highlights", []),
            "risks": result.get("risks", []),
            "suggestions": result.get("suggestions", []),
        }
    except Exception as e:
        print(f"  ⚠️ 简历诊断失败({type(e).__name__})，返回空诊断")
        return {"highlights": [], "risks": [], "suggestions": []}
