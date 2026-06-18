from core.llm import get_model
from core.config import ROOT
from smolagents import ChatMessage, MessageRole


def _load_prompt(name: str) -> str:
    return (ROOT / "prompts" / name).read_text(encoding="utf-8")


def generate_review(position: str, qa_list: list) -> str:
    """根据整场面试的题目/回答/打分，生成复盘报告(Markdown文本)

    qa_list: List[QARecord]，每个含 question、user_answer、score
    """
    # 拼接本场所有问答和打分
    lines = []
    for i, qa in enumerate(qa_list, 1):
        s = qa.score
        score_str = (
            f"得分 {s.total}/5 (准确{s.accuracy} 完整{s.completeness} "
            f"深度{s.depth} 表达{s.clarity})" if s else "未打分"
        )
        lines.append(
            f"第{i}题 [{qa.q_type}]\n"
            f"题目：{qa.question}\n"
            f"回答：{qa.user_answer or '(未作答)'}\n"
            f"评分：{score_str}\n"
            f"评语：{s.comment if s else ''}\n"
        )
    qa_summary = "\n".join(lines)

    prompt = _load_prompt("reviewer.txt").format(
        position=position, qa_summary=qa_summary
    )
    model = get_model()
    messages = [ChatMessage(role=MessageRole.USER, content=prompt)]
    response = model.generate(messages)
    return response.content.strip()
