"""SQLite storage: uploads, sessions, messages. No server needed, the DB is one file."""
import json
import os
import sqlite3

DB_PATH = os.getenv("DATABASE_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "feynman.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS uploads (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    filename      TEXT NOT NULL,
    text          TEXT NOT NULL,
    sections_json TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS sessions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    upload_id     INTEGER NOT NULL REFERENCES uploads(id),
    topic         TEXT NOT NULL,
    material_text TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'active',   -- active | finished
    result_json   TEXT,
    created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(id),
    role       TEXT NOT NULL,                        -- student | ai
    text       TEXT NOT NULL,
    position   INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)


# ----------------------------------------------------------------- uploads
def create_upload(filename, text, sections):
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO uploads (filename, text, sections_json) VALUES (?, ?, ?)",
            (filename, text, json.dumps(sections)),
        )
        return cur.lastrowid


def get_upload(upload_id):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM uploads WHERE id = ?", (upload_id,)).fetchone()


# ----------------------------------------------------------------- sessions
def create_session(upload_id, topic, material_text):
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO sessions (upload_id, topic, material_text) VALUES (?, ?, ?)",
            (upload_id, topic, material_text),
        )
        return cur.lastrowid


def get_session(session_id):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()


def set_status(session_id, status):
    with get_conn() as conn:
        conn.execute("UPDATE sessions SET status = ? WHERE id = ?", (status, session_id))


# ----------------------------------------------------------------- messages
def add_messages(session_id, pairs):
    """pairs = [(role, text), ...]; saved together in one transaction, in order."""
    with get_conn() as conn:
        pos = conn.execute(
            "SELECT COALESCE(MAX(position), 0) FROM messages WHERE session_id = ?", (session_id,)
        ).fetchone()[0]
        for role, text in pairs:
            pos += 1
            conn.execute(
                "INSERT INTO messages (session_id, role, text, position) VALUES (?, ?, ?, ?)",
                (session_id, role, text, pos),
            )


def get_messages(session_id):
    """Returns [{"role": "student"|"ai", "text": "..."}] in order: the shape the AI module expects."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT role, text FROM messages WHERE session_id = ? ORDER BY position", (session_id,)
        ).fetchall()
    return [{"role": r["role"], "text": r["text"]} for r in rows]


# ----------------------------------------------------------------- results
def save_result(session_id, package):
    with get_conn() as conn:
        conn.execute("UPDATE sessions SET result_json = ? WHERE id = ?", (json.dumps(package), session_id))


def get_result(session_id):
    row = get_session(session_id)
    return json.loads(row["result_json"]) if row and row["result_json"] else None
