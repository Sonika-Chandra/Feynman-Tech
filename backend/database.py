"""SQLite storage: uploads, sessions, messages. No server needed, the DB is one file."""
import json
import os
import sqlite3

DB_PATH = os.getenv("DATABASE_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "feynman.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
-- Login tokens never expire: a user stays signed in until they press Log out.
CREATE TABLE IF NOT EXISTS tokens (
    token      TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
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


# Columns added after the first version; added to an existing database file automatically.
MIGRATIONS = [
    ("uploads", "user_id", "INTEGER"),
    ("sessions", "user_id", "INTEGER"),
    ("messages", "needs_whiteboard", "INTEGER NOT NULL DEFAULT 0"),
    ("messages", "image_path", "TEXT"),
    ("messages", "diagram_svg", "TEXT"),
]


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        for table, column, decl in MIGRATIONS:
            cols = [r["name"] for r in conn.execute(f"PRAGMA table_info({table})")]
            if column not in cols:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")


# ----------------------------------------------------------------- users and login tokens
def create_user(name, email, password_hash):
    with get_conn() as conn:
        cur = conn.execute("INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                           (name, email, password_hash))
        return cur.lastrowid


def get_user_by_email(email):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()


def get_user(user_id):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def create_token(user_id, token):
    with get_conn() as conn:
        conn.execute("INSERT INTO tokens (token, user_id) VALUES (?, ?)", (token, user_id))


def get_user_by_token(token):
    with get_conn() as conn:
        return conn.execute(
            "SELECT u.* FROM tokens t JOIN users u ON u.id = t.user_id WHERE t.token = ?", (token,)
        ).fetchone()


def delete_token(token):
    with get_conn() as conn:
        conn.execute("DELETE FROM tokens WHERE token = ?", (token,))


# ----------------------------------------------------------------- uploads
def create_upload(filename, text, sections, user_id=None):
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO uploads (filename, text, sections_json, user_id) VALUES (?, ?, ?, ?)",
            (filename, text, json.dumps(sections), user_id),
        )
        return cur.lastrowid


def get_upload(upload_id):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM uploads WHERE id = ?", (upload_id,)).fetchone()


# ----------------------------------------------------------------- sessions
def create_session(upload_id, topic, material_text, user_id=None):
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO sessions (upload_id, topic, material_text, user_id) VALUES (?, ?, ?, ?)",
            (upload_id, topic, material_text, user_id),
        )
        return cur.lastrowid


def get_session(session_id):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()


def set_status(session_id, status):
    with get_conn() as conn:
        conn.execute("UPDATE sessions SET status = ? WHERE id = ?", (status, session_id))


# ----------------------------------------------------------------- messages
def add_messages(session_id, items):
    """
    items = [(role, text), ...] or [(role, text, {"needs_whiteboard": bool, "image_path": str, "diagram_svg": str}), ...]
    Saved together in one transaction, in order.
    """
    with get_conn() as conn:
        pos = conn.execute(
            "SELECT COALESCE(MAX(position), 0) FROM messages WHERE session_id = ?", (session_id,)
        ).fetchone()[0]
        for item in items:
            role, text = item[0], item[1]
            extra = item[2] if len(item) > 2 else {}
            pos += 1
            conn.execute(
                "INSERT INTO messages (session_id, role, text, position, needs_whiteboard, image_path, diagram_svg) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (session_id, role, text, pos, 1 if extra.get("needs_whiteboard") else 0, extra.get("image_path"), extra.get("diagram_svg")),
            )


def get_messages(session_id):
    """Returns [{"role": "student"|"ai", "text": "..."}] in order: the shape the AI module expects."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT role, text FROM messages WHERE session_id = ? ORDER BY position", (session_id,)
        ).fetchall()
    return [{"role": r["role"], "text": r["text"]} for r in rows]


def get_messages_full(session_id):
    """Same as get_messages plus the extras the screen needs (whiteboard flag, drawing id)."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, role, text, needs_whiteboard, image_path, diagram_svg FROM messages WHERE session_id = ? ORDER BY position",
            (session_id,),
        ).fetchall()
    return [{"id": r["id"], "role": r["role"], "text": r["text"],
             "needs_whiteboard": bool(r["needs_whiteboard"]), "has_drawing": bool(r["image_path"]),
             "diagram_svg": r["diagram_svg"] or ""} for r in rows]


def get_message(message_id):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()


def list_sessions(user_id):
    """A user's past sessions, newest first, with the overall score if there is a result."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT s.id, s.topic, s.status, s.created_at, s.result_json, u.filename "
            "FROM sessions s JOIN uploads u ON u.id = s.upload_id "
            "WHERE s.user_id = ? ORDER BY s.id DESC", (user_id,)
        ).fetchall()
    out = []
    for r in rows:
        overall = None
        if r["result_json"]:
            try:
                overall = json.loads(r["result_json"])["score"]["overall"]
            except (KeyError, TypeError, ValueError):
                pass
        out.append({"session_id": r["id"], "topic": r["topic"], "status": r["status"],
                    "created_at": r["created_at"], "filename": r["filename"], "overall": overall})
    return out


# ----------------------------------------------------------------- results
def save_result(session_id, package):
    with get_conn() as conn:
        conn.execute("UPDATE sessions SET result_json = ? WHERE id = ?", (json.dumps(package), session_id))


def get_result(session_id):
    row = get_session(session_id)
    return json.loads(row["result_json"]) if row and row["result_json"] else None
