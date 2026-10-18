

"""
SQLite logging layer for the chatbot. Every message -- both what the user
sent and what the bot replied -- is logged as a row in a single `messages`
table. This is what makes the analytics dashboard real: every number it
shows is computed from these rows with a SQL query, not incremented in
browser JavaScript like the original starter code did.

The same functions here are used by both server.py (web chat) and
telegram_bot.py (Telegram integration) -- one shared log for both front
ends, which is also what makes the per-disease-style "agreement" analytics
(here: canned-reply rate, feedback rate) meaningful across platforms.
"""

import json
import os
import sqlite3      # used for the database connection and queries
from contextlib import contextmanager        # used to make a context manager for the database connection
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))       # get the base directory of the project
DB_PATH = os.path.join(BASE_DIR, "data", "chatbot.db")    

@contextmanager
def get_connection():
    
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_db():      
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('user', 'bot')),
                text TEXT NOT NULL,
                sentiment_label TEXT,
                sentiment_compound REAL,
                intent TEXT,
                intent_confidence REAL,
                entities TEXT,
                used_canned_reply INTEGER DEFAULT 0,
                response_time_ms REAL,
                feedback TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_session ON messages(session_id)")
    print(f"Database ready at {DB_PATH}")

def log_message(session_id, role, text, sentiment=None, intent=None, entities=None,
                 used_canned_reply=False, response_time_ms=None):
    """Logs one message row. Returns the new row's id (used later to attach feedback)."""
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO messages
               (session_id, timestamp, role, text, sentiment_label, sentiment_compound,
                intent, intent_confidence, entities, used_canned_reply, response_time_ms)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                session_id,
                datetime.now(timezone.utc).isoformat(),
                role,
                text,
                sentiment["label"] if sentiment else None,
                sentiment["compound"] if sentiment else None,
                intent["intent"] if intent else None,
                intent["confidence"] if intent else None,
                json.dumps(entities) if entities is not None else None,
                1 if used_canned_reply else 0,
                response_time_ms,
            ),
        )
        return cur.lastrowid

def get_recent_history(session_id, limit=6):
    """
    Returns the last `limit` messages for this session, oldest first -- used
    to give Gemini real conversation context instead of answering each
    message in isolation.
    """
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT role, text FROM messages
               WHERE session_id = ?
               ORDER BY id DESC LIMIT ?""",
            (session_id, limit),
        ).fetchall()
    return [{"role": r["role"], "text": r["text"]} for r in reversed(rows)]

def get_full_history(session_id):
    """
    Returns every message for a session, in order -- used when the frontend
    switches to a past conversation and needs to repopulate the whole chat
    window. (get_recent_history, used internally for Gemini context, stays
    capped at a small window -- this one is uncapped, for display only.)
    """
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT id, role, text, timestamp FROM messages
               WHERE session_id = ?
               ORDER BY id ASC""",
            (session_id,),
        ).fetchall()
    return [
        {"id": r["id"], "role": r["role"], "text": r["text"], "timestamp": r["timestamp"]}
        for r in rows
    ]

def set_feedback(message_id, feedback_value):
    """feedback_value must be 'up' or 'down'."""
    with get_connection() as conn:
        cur = conn.execute(
            "UPDATE messages SET feedback = ? WHERE id = ? AND role = 'bot'",
            (feedback_value, message_id),
        )
        return cur.rowcount > 0

def get_analytics():
    """Every number here comes from a real SQL query over logged messages."""
    with get_connection() as conn:
        total_conversations = conn.execute(
            "SELECT COUNT(DISTINCT session_id) AS c FROM messages"
        ).fetchone()["c"]

        total_user_messages = conn.execute(
            "SELECT COUNT(*) AS c FROM messages WHERE role = 'user'"
        ).fetchone()["c"]

        avg_response_time = conn.execute(
            "SELECT AVG(response_time_ms) AS a FROM messages WHERE role = 'bot' AND response_time_ms IS NOT NULL"
        ).fetchone()["a"]

        sentiment_rows = conn.execute(
            """SELECT sentiment_label, COUNT(*) AS c FROM messages
               WHERE role = 'user' AND sentiment_label IS NOT NULL
               GROUP BY sentiment_label"""
        ).fetchall()

        intent_rows = conn.execute(
            """SELECT intent, COUNT(*) AS c FROM messages
               WHERE role = 'user' AND intent IS NOT NULL
               GROUP BY intent ORDER BY c DESC"""
        ).fetchall()

        canned_vs_llm = conn.execute(
            """SELECT used_canned_reply, COUNT(*) AS c FROM messages
               WHERE role = 'bot' GROUP BY used_canned_reply"""
        ).fetchall()

        feedback_rows = conn.execute(
            """SELECT feedback, COUNT(*) AS c FROM messages
               WHERE role = 'bot' AND feedback IS NOT NULL
               GROUP BY feedback"""
        ).fetchall()

    return {
        "total_conversations": total_conversations,
        "total_messages": total_user_messages,
        "avg_response_time_ms": round(avg_response_time, 1) if avg_response_time else None,
        "sentiment_distribution": {r["sentiment_label"]: r["c"] for r in sentiment_rows},
        "intent_distribution": {r["intent"]: r["c"] for r in intent_rows},
        "canned_reply_vs_llm": {
            ("canned" if r["used_canned_reply"] else "llm"): r["c"] for r in canned_vs_llm
        },
        "feedback": {r["feedback"]: r["c"] for r in feedback_rows},
    }

