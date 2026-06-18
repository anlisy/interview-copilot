import sqlite3
import json
import uuid
from datetime import datetime
from core.config import DB_PATH


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                title TEXT,
                company TEXT,
                position TEXT,
                resume_name TEXT,
                resume_content TEXT,
                jd_content TEXT,
                config TEXT,
                qa_list TEXT,
                status TEXT,
                overall_score REAL,
                review_report TEXT,
                created_at TEXT,
                finished_at TEXT
            )
        """)


def save_session(s: dict):
    """保存或更新一场面试（s 为 dict）"""
    with _conn() as c:
        c.execute("""
            INSERT OR REPLACE INTO sessions
            (session_id, title, company, position, resume_name, resume_content,
             jd_content, config, qa_list, status, overall_score, review_report,
             created_at, finished_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            s["session_id"], s["title"], s["company"], s["position"],
            s["resume_name"], s["resume_content"], s["jd_content"],
            json.dumps(s["config"], ensure_ascii=False),
            json.dumps(s["qa_list"], ensure_ascii=False),
            s["status"], s.get("overall_score", 0), s.get("review_report", ""),
            s["created_at"], s.get("finished_at", ""),
        ))


def list_sessions():
    """返回所有面试记录（按时间倒序）"""
    with _conn() as c:
        rows = c.execute(
            "SELECT session_id, title, status, overall_score, created_at "
            "FROM sessions ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def get_session(session_id: str):
    """读取一场完整面试"""
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM sessions WHERE session_id=?", (session_id,)
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["config"] = json.loads(d["config"])
        d["qa_list"] = json.loads(d["qa_list"])
        return d


def new_session_id():
    return uuid.uuid4().hex[:12]
