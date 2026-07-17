"""Streamlit 前端：纯 UI 层，通过 HTTP 调用 FastAPI 后端。
L3-a: 支持追问循环。回答输入抽象为 get_answer_input()，未来可接语音转文字。
"""
import requests
import streamlit as st
from datetime import datetime
from storage import db

API = "http://localhost:8000"

st.set_page_config(page_title="Interview Copilot", page_icon="🎯", layout="wide")
db.init_db()

PRESETS = ["均衡型", "重项目型", "重八股型"]
MAX_FOLLOWUP = 2


def strip_md_fence(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        lines = t.split("\n")[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines)
    return text


def get_answer_input(label: str, key: str, height: int = 150) -> str:
    """回答输入。当前为文字；未来接语音转文字只需在此加语音组件，下游零改动。"""
    return st.text_area(label, key=key, height=height)


page = st.sidebar.radio("导航", ["开始新面试", "历史记录"])

# ============ 页面1：开始新面试 ============
if page == "开始新面试":
    st.title("🎯 开始一场模拟面试")

    if "session" not in st.session_state:
        col1, col2, col3 = st.columns(3)
        company = col1.text_input("公司", "阿里")
        position = col2.text_input("岗位", "AI应用研发工程师")
        resume_name = col3.text_input("简历名", "我的简历")

        resume = st.text_area("简历内容", height=180, placeholder="粘贴你的简历文本...")
        jd = st.text_area("岗位JD", height=120, placeholder="粘贴目标岗位JD...")

        c1, c2 = st.columns(2)
        total = c1.slider("题目数量", 3, 12, 5)
        preset = c2.selectbox("题型偏好", PRESETS)

        if st.button("生成题目，开始面试", type="primary"):
            if not resume.strip() or not jd.strip():
                st.error("请填写简历和JD")
            else:
                with st.spinner("AI面试官正在出题..."):
                    resp = requests.post(f"{API}/api/interview/start", json={
                        "resume": resume, "jd": jd,
                        "total_questions": total, "preset": preset,
                    }, timeout=180)
                if resp.status_code != 200:
                    st.error(f"出题失败：{resp.status_code} {resp.text}")
                else:
                    data = resp.json()
                    qs = data["questions"]
                    st.session_state.session = {
                        "session_id": data["session_id"],
                        "company": company, "position": position,
                        "resume_name": resume_name,
                        "resume_content": resume, "jd_content": jd,
                        "config": {"total": total, "preset": preset},
                        "questions": qs,
                        "answers": [None] * len(qs),
                        "scores": [None] * len(qs),
                        "followups": [[] for _ in qs],
                        "cur": 0,
                        "followup_count": 0,
                        "current_followup": None,
                        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    }
                    st.rerun()

    else:
        s = st.session_state.session
        qs = s["questions"]
        cur = s["cur"]
        st.subheader(f"{s['company']} - {s['position']}")

        if cur < len(qs):
            st.progress(cur / len(qs), text=f"第 {cur+1}/{len(qs)} 题")
            q = qs[cur]
            st.markdown(f"**【{q.get('type')}|{q.get('difficulty')}】** {q.get('question')}")

            if s["answers"][cur]:
                st.markdown(f"**你的回答**：{s['answers'][cur]}")

            for fu in s["followups"][cur]:
                st.markdown(f"> 🔁 **追问**：{fu['q']}")
                st.markdown(f"> 　 你的回答：{fu['a']}")

            in_followup = s["current_followup"] is not None
            scored = s["scores"][cur] is not None

            if in_followup:
                # ===== 答追问态 =====
                st.markdown(f"🔁 **追问**：{s['current_followup']}")
                fu_ans = get_answer_input("你的追问回答", key=f"fu_{cur}_{s['followup_count']}")
                if st.button("提交追问回答", type="primary"):
                    if not fu_ans.strip():
                        st.warning("请先输入回答")
                    else:
                        is_last = (cur == len(qs) - 1)
                        with st.spinner("面试官思考中..."):
                            resp = requests.post(f"{API}/api/interview/answer2", json={
                                "session_id": s["session_id"],
                                "q_type": q.get("type"),
                                "question": s["current_followup"],
                                "answer": fu_ans,
                                "is_last": is_last,
                                "is_followup": True,
                                "followup_count": s["followup_count"],
                                "max_followup": MAX_FOLLOWUP,
                            }, timeout=120)
                        if resp.status_code != 200:
                            st.error(f"失败：{resp.status_code} {resp.text}")
                        else:
                            data = resp.json()
                            s["followups"][cur].append({
                                "q": s["current_followup"], "a": fu_ans,
                            })
                            if data["need_followup"]:
                                s["current_followup"] = data["followup_question"]
                                s["followup_count"] = data["next_followup_count"]
                            else:
                                s["current_followup"] = None
                            st.session_state.session = s
                            st.rerun()

            elif scored:
                # ===== 已评分态 =====
                score = s["scores"][cur]
                st.success(f"本题得分：{score['total']}/5")
                st.write(f"准确{score['accuracy']} 完整{score['completeness']} "
                         f"深度{score['depth']} 表达{score['clarity']}")
                st.info(score['comment'])
                if st.button("下一题 ▶", type="primary"):
                    s["cur"] += 1
                    s["followup_count"] = 0
                    s["current_followup"] = None
                    st.session_state.session = s
                    st.rerun()

            else:
                # ===== 答主问题态 =====
                ans = get_answer_input("你的回答", key=f"ans_{cur}", height=180)
                if st.button("提交回答", type="primary"):
                    if not ans.strip():
                        st.warning("请先输入回答")
                    else:
                        is_last = (cur == len(qs) - 1)
                        with st.spinner("面试官正在评分..."):
                            resp = requests.post(f"{API}/api/interview/answer2", json={
                                "session_id": s["session_id"],
                                "q_type": q.get("type"),
                                "question": q.get("question"),
                                "answer": ans,
                                "is_last": is_last,
                                "is_followup": False,
                                "followup_count": 0,
                                "max_followup": MAX_FOLLOWUP,
                            }, timeout=120)
                        if resp.status_code != 200:
                            st.error(f"评分失败：{resp.status_code} {resp.text}")
                        else:
                            data = resp.json()
                            s["answers"][cur] = ans
                            s["scores"][cur] = data["score"]
                            if data["need_followup"]:
                                s["current_followup"] = data["followup_question"]
                                s["followup_count"] = data["next_followup_count"]
                            st.session_state.session = s
                            st.rerun()

        else:
            # ===== 复盘 =====
            st.progress(1.0, text="面试完成")
            st.success("🎉 面试完成！")
            if "review" not in s:
                qa_list = [
                    {
                        "order": i + 1,
                        "q_type": qs[i].get("type"),
                        "question": qs[i].get("question"),
                        "user_answer": s["answers"][i] or "",
                        "score": s["scores"][i],
                    }
                    for i in range(len(qs))
                ]
                with st.spinner("正在生成复盘报告..."):
                    resp = requests.post(f"{API}/api/interview/review", json={
                        "session_id": s["session_id"],
                        "position": s["position"],
                        "qa_list": qa_list,
                    }, timeout=180)
                if resp.status_code != 200:
                    st.error(f"复盘失败：{resp.status_code} {resp.text}")
                else:
                    review = strip_md_fence(resp.json()["report"])
                    valid = [sc["total"] for sc in s["scores"] if sc]
                    avg = sum(valid) / len(valid) if valid else 0
                    s["review"] = review
                    s["overall_score"] = round(avg, 1)
                    db.save_session({
                        "session_id": s["session_id"],
                        "title": f"{s['company']}-{s['position']}-{s['resume_name']}",
                        "company": s["company"], "position": s["position"],
                        "resume_name": s["resume_name"],
                        "resume_content": s["resume_content"],
                        "jd_content": s["jd_content"],
                        "config": s["config"],
                        "qa_list": [
                            {"type": qs[i].get("type"), "question": qs[i].get("question"),
                             "answer": s["answers"][i] or "",
                             "score": s["scores"][i],
                             "followups": s["followups"][i]}
                            for i in range(len(qs))
                        ],
                        "status": "已完成",
                        "overall_score": s["overall_score"],
                        "review_report": review,
                        "created_at": s["created_at"],
                        "finished_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    })
                    st.session_state.session = s
                    st.rerun()

            if "review" in s:
                st.metric("本场总分", f"{s['overall_score']}/5")
                st.markdown(s["review"])
                if st.button("结束并返回"):
                    del st.session_state.session
                    st.rerun()
# ============ 页面2：历史记录 ============
else:
    st.title("📋 历史面试记录")
    sessions = db.list_sessions()
    if not sessions:
        st.info("还没有面试记录，去「开始新面试」吧")
    for row in sessions:
        with st.expander(f"{row['title']}  ({row['created_at']})  总分 {row['overall_score']}/5"):
            full = db.get_session(row["session_id"])
            st.markdown(f"**岗位**：{full['position']}")
            for i, qa in enumerate(full["qa_list"], 1):
                sc = qa.get("score")
                st.markdown(f"**第{i}题 [{qa['type']}]** {qa['question']}")
                st.write(f"回答：{qa['answer'] or '(未答)'}")
                for fu in qa.get("followups", []):
                    st.markdown(f"　🔁 追问：{fu['q']}")
                    st.markdown(f"　　回答：{fu['a']}")
                if sc:
                    st.caption(f"得分 {sc['total']}/5 | {sc['comment']}")
                st.divider()
            st.markdown("### 复盘报告")
            st.markdown(full["review_report"])


