"""答题助手：输入面试题，RAG检索知识库生成参考答案。"""
from core.config import ROOT
from core.llm import generate_with_retry
from tools.knowledge_tools import search_knowledge


def _load_prompt(name: str) -> str:
    return (ROOT / "prompts" / name).read_text(encoding="utf-8")


def _is_relevant(question: str, ref_text: str) -> bool:
    """让 LLM 判断检索到的资料是否真能回答问题（比相似度阈值准）。
    避免'都是技术话题'导致的高相似度误判。失败则保守返回 False。"""
    try:
        prompt = (
            f"问题：{question}\n\n"
            f"资料：\n{ref_text}\n\n"
            f"上面的资料能否直接回答这个问题？只回答 是 或 否。"
        )
        ans = generate_with_retry(prompt, model_id="glm-4-flash").strip()
        return "是" in ans[:5]
    except Exception:
        return False


def answer_question(question: str, model_id: str = "glm-4-plus") -> dict:
    """为一个问题生成参考答案。
    RAG检索所有分类知识库，基于检索内容生成答案。
    返回 {answer, source, refs}。source: 'kb'有知识库支撑 / 'ai'纯AI生成。
    """
    # 检索所有分类（八股/面经/实习/项目），取最相关的
    refs = []
    try:
        for cat in ["八股", "面经", "实习", "项目"]:
            hits = search_knowledge(question, category=cat, top_k=1)
            refs += [(h["similarity"], h) for h in hits]
        # 按相似度排序，取前3
        refs.sort(key=lambda x: x[0], reverse=True)
        refs = [h for sim, h in refs[:3] if sim > 0.5]   # 相似度阈值(标定:相关~0.6/无关~0.3)
    except Exception as e:
        print(f"  ⚠️ 检索失败({type(e).__name__})")
        refs = []

    # 构造参考资料
    if refs:
        ref_text = "\n".join(
            f"- {h['metadata'].get('question','')}: {h['document'][:150]}"
            for h in refs
        )
        # LLM 相关性判断：资料真能回答问题才算 kb，否则当无参考
        if _is_relevant(question, ref_text):
            source = "kb"
        else:
            print(f"  ℹ️ 检索到内容但不相关，判为无参考")
            ref_text = "（知识库无相关内容）"
            source = "ai"
    else:
        ref_text = "（知识库无相关内容）"
        source = "ai"

    # 生成答案
    try:
        prompt = _load_prompt("answer_question.txt").format(
            question=question, references=ref_text)
        answer = generate_with_retry(prompt, model_id=model_id).strip()
    except Exception as e:
        answer = f"（答案生成失败: {type(e).__name__}）"

    return {"answer": answer, "source": source, "ref_count": len(refs)}


def answer_batch(questions: list, on_answer=None) -> list:
    """批量答题，支持流式回调（每答完一题立刻回调）。"""
    results = []
    n = len(questions)
    for idx, q in enumerate(questions):
        r = answer_question(q)
        r["question"] = q
        results.append(r)
        if on_answer:
            on_answer(idx + 1, n, r)
    return results
