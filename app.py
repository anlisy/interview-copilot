import streamlit as st
from datetime import datetime

from core.models import InterviewConfig
from tools.question_tools import generate_questions
from tools.score_tools import score_answer
from tools.review_tools import generate_review
from storage import db

st.set_page_config(page_title="Interview Copilot", page_icon="🎯", layout="wide")
db.init_db()

# ---------- 预设题型比例模板 ----------
PRESETS = {
    "均衡型": {"RESUME_PROJECT": 30, "RESUME_INTERNSHIP": 15, "JAVA_BASIC": 20,
              "AI_BASIC": 20, "CODING": 10, "BEHAVIOR": 5},
    "重项目型": {"RESUME_PROJECT": 40, "RESUME_INTERNSHIP": 25, "JAVA_BASIC": 10,
               "AI_BASIC": 15, "CODING": 5, "BEHAVIOR": 5},
    "重八股型": {"RESUME_PROJECT": 15, "RESUME_INTERNSHIP": 10, "JAVA_BASIC": 35,
               "AI_BASIC": 30, "CODING": 5, "BEHAVIOR": 5},
}

# ---------- 侧边栏：导航 ----------
page = st.sidebar.radio("导航", ["开始新面试", "历史记录"])

# ============ 页面1：开始新面试 ============
if page == "开始新面试":
    st.title("🎯 开始一场模拟面试")

    if "session" not in st.session_state:
        # 配置阶段
        col1, col2, col3 = st.columns(3)
        company = col1.text_input("公司", "阿里")
        position = col2.text_input("岗位", "AI应用研发工程师")
        resume_name = col3.text_input("简历名", "我的简历")

        resume = st.text_area("简历内容", height=180,
                              placeholder="粘贴你的简历文本...")
        jd = st.text_area("岗位JD", height=120, placeholder="粘贴目标岗位JD...")

        c1, c2 = st.columns(2)
        total = c1.slider("题目数量", 3, 12, 5)
        preset = c2.selectbox("题型偏好", list(PRESETS.keys()))

        if st.button("生成题目，开始面试", type="primary"):
            if not resume.strip() or not jd.strip():
                st.error("请填写简历和JD")
            else:
                with st.spinner("AI面试官正在出题..."):
                    qs = generate_questions(resume, jd, total, PRESETS[preset])
                st.session_state.session = {
                    "session_id": db.new_session_id(),
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
        # 答题阶段
        s = st.session_state.session
        qs = s["questions"]
        cur = s["cur"]
        st.subheader(f"{s['company']} - {s['position']}")
        st.progress((cur) / len(qs), text=f"第 {cur+1}/{len(qs)} 题")

        if cur < len(qs):
            q = qs[cur]
            st.markdown(f"**【{q.get('type')}|{q.get('difficulty')}】** {q.get('question')}")
            ans = st.text_area("你的回答", key=f"ans_{cur}", height=180)

            if st.button("提交回答", type="primary"):
                with st.spinner("面试官正在评分..."):
                    score = score_answer(q.get("type"), q.get("question"), ans)
                s["answers"][cur] = ans
                s["scores"][cur] = score
                # 显示本题打分
                st.success(f"本题得分：{score.total}/5")
                st.write(f"准确{score.accuracy} 完整{score.completeness} "
                        f"深度{score.depth} 表达{score.clarity}")
                st.info(score.comment)
                s["cur"] += 1
                st.session_state.session = s
                st.button("下一题")  # 点任意交互会 rerun

        else:
            # 面试结束，生成复盘
            st.success("🎉 面试完成！")
            if "review" not in s:
                from core.models import QARecord
                qa_records = [
                    QARecord(order=i+1, q_type=qs[i].get("type"),
                            question=qs[i].get("question"),
                            user_answer=s["answers"][i] or "",
                            score=s["scores"][i])
                    for i in range(len(qs))
                ]
                with st.spinner("正在生成复盘报告..."):
                    review = generate_review(s["position"], qa_records)
                avg = sum(sc.total for sc in s["scores"] if sc) / len(qs)
                s["review"] = review
                s["overall_score"] = round(avg, 1)
                # 存数据库
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
                         "score": vars(s["scores"][i]) if s["scores"][i] else None}
                        for i in range(len(qs))
                    ],
                    "status": "已完成",
                    "overall_score": s["overall_score"],
                    "review_report": review,
                    "created_at": s["created_at"],
                    "finished_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                })
                st.session_state.session = s

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
