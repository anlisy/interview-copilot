"""Streamlit 前端：纯 UI 层，所有面试逻辑通过 HTTP 调用 FastAPI 后端。"""
import requests
import streamlit as st
from datetime import datetime
from storage import db

API = "http://localhost:8000"

st.set_page_config(page_title="Interview Copilot", page_icon="🎯", layout="wide")
db.init_db()

PRESETS = ["均衡型", "重项目型", "重八股型"]


def strip_md_fence(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        lines = t.split("\n")[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines)
    return text


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
                        "cur": 0,
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

            # 显示题目
            st.markdown(f"**【{q.get('type')}|{q.get('difficulty')}】** {q.get('question')}")

            # 这一题是否已经答过并评分了？
            already_scored = s["scores"][cur] is not None

            if not already_scored:
                # ===== 还没答：显示输入框 + 提交按钮 =====
                ans = st.text_area("你的回答", key=f"ans_{cur}", height=180)
                if st.button("提交回答", type="primary"):
                    if not ans.strip():
                        st.warning("请先输入回答")
                    else:
                        is_last = (cur == len(qs) - 1)
                        with st.spinner("面试官正在评分..."):
                            resp = requests.post(f"{API}/api/interview/answer", json={
                                "session_id": s["session_id"],
                                "q_type": q.get("type"),
                                "question": q.get("question"),
                                "answer": ans,
                                "is_last": is_last,
                            }, timeout=120)
                        if resp.status_code != 200:
                            st.error(f"评分失败：{resp.status_code} {resp.text}")
                        else:
                            score = resp.json()["score"]
                            s["answers"][cur] = ans
                            s["scores"][cur] = score
                            st.session_state.session = s
                            st.rerun()   # ← 关键：评分存好后重跑，进入"已评分"显示态
            else:
                # ===== 已答已评分：显示回答 + 评分 + 下一题按钮 =====
                score = s["scores"][cur]
                st.text_area("你的回答", value=s["answers"][cur], height=120,
                             disabled=True, key=f"answered_{cur}")
                st.success(f"本题得分：{score['total']}/5")
                st.write(f"准确{score['accuracy']} 完整{score['completeness']} "
                         f"深度{score['depth']} 表达{score['clarity']}")
                st.info(score['comment'])
                if st.button("下一题 ▶", type="primary"):
                    s["cur"] += 1
                    st.session_state.session = s
                    st.rerun()   # ← 关键：推进后重跑，显示下一题

        else:
            # ===== 所有题答完，生成复盘 =====
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
                             "score": s["scores"][i]}
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
                if sc:
                    st.caption(f"得分 {sc['total']}/5 | {sc['comment']}")
                st.divider()
            st.markdown("### 复盘报告")
            st.markdown(full["review_report"])
