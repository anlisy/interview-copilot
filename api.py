"""FastAPI 后端：所有面试流程通过 Supervisor 调度，按 session 维护状态。

L2-b 变化：会话状态存 Redis。Supervisor 是"借出-用完-归还"模式，
每次操作后必须 session_manager.save() 把新状态写回，否则状态丢失。
"""
from dataclasses import asdict
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from core.models import QARecord, Score
from agents.session_manager import session_manager

app = FastAPI(title="Interview Copilot L2-b API")

PRESETS = {
    "均衡型": {"RESUME_PROJECT": 30, "RESUME_INTERNSHIP": 15, "JAVA_BASIC": 20,
              "AI_BASIC": 20, "CODING": 10, "BEHAVIOR": 5},
    "重项目型": {"RESUME_PROJECT": 40, "RESUME_INTERNSHIP": 25, "JAVA_BASIC": 10,
               "AI_BASIC": 15, "CODING": 5, "BEHAVIOR": 5},
    "重八股型": {"RESUME_PROJECT": 15, "RESUME_INTERNSHIP": 10, "JAVA_BASIC": 35,
               "AI_BASIC": 30, "CODING": 5, "BEHAVIOR": 5},
}


# ---------- 请求/响应模型 ----------
class StartReq(BaseModel):
    resume: str
    jd: str
    total_questions: int = 5
    preset: str = "均衡型"


class StartResp(BaseModel):
    session_id: str
    state: str
    questions: list


class AnswerReq(BaseModel):
    session_id: str
    q_type: str
    question: str
    answer: str
    is_last: bool


class AnswerResp(BaseModel):
    state: str
    score: dict


class ReviewReq(BaseModel):
    session_id: str
    position: str
    qa_list: list


class ReviewResp(BaseModel):
    state: str
    report: str


# ---------- 1. 出题 ----------
@app.post("/api/interview/start", response_model=StartResp)
def api_start(req: StartReq):
    type_ratio = PRESETS.get(req.preset, PRESETS["均衡型"])
    sid = session_manager.create()
    sup = session_manager.get(sid)
    questions = sup.run_generate(req.resume, req.jd, req.total_questions, type_ratio)
    session_manager.save(sid, sup)   # ← L2-b: 写回 Redis（state 已变为 ASKING）
    return StartResp(session_id=sid, state=sup.state.value, questions=questions)


# ---------- 2. 评分 ----------
@app.post("/api/interview/answer", response_model=AnswerResp)
def api_answer(req: AnswerReq):
    try:
        sup = session_manager.get(req.session_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    try:
        score = sup.run_score(req.q_type, req.question, req.answer, req.is_last)
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    session_manager.save(req.session_id, sup)   # ← L2-b: 写回 Redis
    return AnswerResp(state=sup.state.value, score=asdict(score))


# ---------- 3. 复盘 ----------
@app.post("/api/interview/review", response_model=ReviewResp)
def api_review(req: ReviewReq):
    try:
        sup = session_manager.get(req.session_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))

    qa_list = [
        QARecord(
            order=item["order"],
            q_type=item["q_type"],
            question=item["question"],
            user_answer=item["user_answer"],
            score=Score(**item["score"]) if item.get("score") else None,
        )
        for item in req.qa_list
    ]
    try:
        report = sup.run_review(req.position, qa_list)
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))

    resp = ReviewResp(state=sup.state.value, report=report)
    session_manager.drop(req.session_id)   # 复盘完成，清理会话
    return resp


# ---------- 调试：查状态 ----------
@app.get("/api/interview/{sid}/state")
def api_state(sid: str):
    try:
        sup = session_manager.get(sid)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"session_id": sid, "state": sup.state.value}


# ---------- L3-a: 支持追问的评分接口 ----------
class Answer2Req(BaseModel):
    session_id: str
    q_type: str
    question: str
    answer: str
    is_last: bool
    is_followup: bool = False
    followup_count: int = 0
    max_followup: int = 2


class Answer2Resp(BaseModel):
    state: str
    score: dict
    need_followup: bool
    followup_question: str | None
    followup_reason: str
    next_followup_count: int


@app.post("/api/interview/answer2", response_model=Answer2Resp)
def api_answer2(req: Answer2Req):
    """评分 + 追问决策。支持主问题和追问两种回答。"""
    try:
        sup = session_manager.get(req.session_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))

    try:
        q_type = "追问" if req.is_followup else req.q_type
        score = sup.run_score_only(q_type, req.question, req.answer)
        need, fq, reason = sup.decide_followup(
            req.question, req.answer, asdict(score),
            req.followup_count, req.max_followup
        )
        if need:
            sup.go_followup()
            next_count = req.followup_count + 1
        else:
            sup.go_next_or_finish(req.is_last)
            next_count = 0
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))

    session_manager.save(req.session_id, sup)

    return Answer2Resp(
        state=sup.state.value,
        score=asdict(score),
        need_followup=need,
        followup_question=fq,
        followup_reason=reason,
        next_followup_count=next_count,
    )
