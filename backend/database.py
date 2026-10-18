"""SQLite storage: uploads, sessions, messages. No server needed, the DB is one file."""
import datetime
import json
import os
import sqlite3

import integrity

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
    ("sessions", "time_limit", "INTEGER NOT NULL DEFAULT 0"),
    ("sessions", "integrity_json", "TEXT"),
    ("sessions", "confidence", "INTEGER"),
    ("sessions", "feedback_json", "TEXT"),
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
def create_session(upload_id, topic, material_text, user_id=None, time_limit=0, confidence=None):
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO sessions (upload_id, topic, material_text, user_id, time_limit, confidence) VALUES (?, ?, ?, ?, ?, ?)",
            (upload_id, topic, material_text, user_id, int(time_limit or 0), confidence),
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
    Saved together in one transaction, in order. Returns the new message ids.
    """
    ids = []
    with get_conn() as conn:
        pos = conn.execute(
            "SELECT COALESCE(MAX(position), 0) FROM messages WHERE session_id = ?", (session_id,)
        ).fetchone()[0]
        for item in items:
            role, text = item[0], item[1]
            extra = item[2] if len(item) > 2 else {}
            pos += 1
            cur = conn.execute(
                "INSERT INTO messages (session_id, role, text, position, needs_whiteboard, image_path, diagram_svg) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (session_id, role, text, pos, 1 if extra.get("needs_whiteboard") else 0, extra.get("image_path"), extra.get("diagram_svg")),
            )
            ids.append(cur.lastrowid)
    return ids


def delete_message(message_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM messages WHERE id = ?", (message_id,))


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


def save_integrity(session_id, state):
    with get_conn() as conn:
        conn.execute("UPDATE sessions SET integrity_json = ? WHERE id = ?", (json.dumps(state), session_id))


def list_sessions(user_id):
    """A user's past sessions, newest first, with the overall score if there is a result."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT s.id, s.topic, s.status, s.created_at, s.result_json, s.integrity_json, u.filename "
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
        flagged = integrity.verdict(integrity.load(r["integrity_json"]))["flagged"]
        out.append({"session_id": r["id"], "topic": r["topic"], "status": r["status"],
                    "created_at": r["created_at"], "filename": r["filename"], "overall": overall,
                    "flagged": flagged, "badge": integrity.badge(overall, flagged)})
    return out


# ----------------------------------------------------------------- results
def save_result(session_id, package):
    with get_conn() as conn:
        conn.execute("UPDATE sessions SET result_json = ? WHERE id = ?", (json.dumps(package), session_id))


def get_result(session_id):
    row = get_session(session_id)
    return json.loads(row["result_json"]) if row and row["result_json"] else None


def attempts_for(user_id, filename, topic):
    """Every scored attempt this user made on the same file and topic, oldest first (stored data only, no AI)."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT s.id, s.created_at, s.result_json FROM sessions s JOIN uploads u ON u.id = s.upload_id "
            "WHERE s.user_id = ? AND u.filename = ? AND s.topic = ? AND s.result_json IS NOT NULL ORDER BY s.id",
            (user_id, filename, topic)).fetchall()
    out = []
    for r in rows:
        try:
            sc = json.loads(r["result_json"])["score"]
            out.append({"session_id": r["id"], "created_at": r["created_at"], "overall": sc["overall"],
                        "scores": {k: v["score"] for k, v in sc["scores"].items()}})
        except (KeyError, TypeError, ValueError):
            continue
    return out


def save_feedback(session_id, feedback):
    with get_conn() as conn:
        conn.execute("UPDATE sessions SET feedback_json = ? WHERE id = ?", (json.dumps(feedback), session_id))


def stats():
    """Anonymous totals for the evidence slide: no names, no emails, no answers."""
    with get_conn() as conn:
        rows = conn.execute("SELECT user_id, upload_id, topic, confidence, result_json, feedback_json, integrity_json FROM sessions "
                            "WHERE result_json IS NOT NULL ORDER BY id").fetchall()
        uploads = {r["id"]: r["filename"] for r in conn.execute("SELECT id, filename FROM uploads")}
    scored, pred, useful, conf_after, groups, flagged = [], [], [], [], {}, 0
    for r in rows:
        try:
            overall = json.loads(r["result_json"])["score"]["overall"]
        except (KeyError, TypeError, ValueError):
            continue
        if integrity.verdict(integrity.load(r["integrity_json"]))["flagged"]:
            flagged += 1
            continue
        scored.append(overall)
        if r["confidence"] is not None:
            pred.append((r["confidence"] * 10, overall))
        try:
            fb = json.loads(r["feedback_json"]) if r["feedback_json"] else {}
        except ValueError:
            fb = {}
        if fb.get("useful"): useful.append(fb["useful"])
        if fb.get("confidence_after") is not None: conf_after.append(fb["confidence_after"])
        groups.setdefault((r["user_id"], uploads.get(r["upload_id"]), r["topic"]), []).append(overall)
    gains = [g[-1] - g[0] for g in groups.values() if len(g) >= 2]
    avg = lambda xs: round(sum(xs) / len(xs), 1) if xs else None
    return {
        "sessions": len(scored), "students": len({k[0] for k in groups}), "flagged": flagged,
        "average_score": avg(scored),
        "retried_topics": len(gains), "average_gain_on_retry": avg(gains),
        "improved_on_retry": sum(1 for x in gains if x > 0),
        "confidence_rated": len(pred), "average_predicted": avg([p for p, _ in pred]), "average_actual_when_predicted": avg([a for _, a in pred]),
        "overconfident": sum(1 for p, a in pred if p - a >= 15),
        "feedback_count": len(useful), "average_usefulness": avg(useful),
    }


def _window_sql(since, until):
    """WHERE parts for a time window. since/until are naive UTC datetimes (created_at is stored in UTC) or None."""
    parts, args = [], []
    if since is not None:
        parts.append("s.created_at >= ?"); args.append(since.strftime("%Y-%m-%d %H:%M:%S"))
    if until is not None:
        parts.append("s.created_at <= ?"); args.append(until.strftime("%Y-%m-%d %H:%M:%S"))
    return (" AND " + " AND ".join(parts)) if parts else "", args


def feedback_rows(since=None, until=None):
    """One row per session that has feedback or a confidence rating. No names, no emails. Optional time window."""
    where, args = _window_sql(since, until)
    with get_conn() as conn:
        rows = conn.execute("SELECT s.id, s.created_at, s.topic, s.confidence, s.feedback_json, s.result_json, s.integrity_json, u.filename "
                            "FROM sessions s JOIN uploads u ON u.id = s.upload_id WHERE s.result_json IS NOT NULL" + where + " ORDER BY s.id", args).fetchall()
    out = []
    for r in rows:
        try:
            overall = json.loads(r["result_json"])["score"]["overall"]
            fb = json.loads(r["feedback_json"]) if r["feedback_json"] else {}
        except (KeyError, TypeError, ValueError):
            continue
        if r["confidence"] is None and not fb:
            continue
        out.append({"session_id": r["id"], "date": r["created_at"], "file": r["filename"], "topic": r["topic"],
                    "confidence_before_pct": None if r["confidence"] is None else r["confidence"] * 10,
                    "score": overall, "useful_1_to_5": fb.get("useful"), "confidence_after_pct": None if fb.get("confidence_after") is None else fb["confidence_after"] * 10,
                    "tags": "; ".join(fb.get("tags") or []), "would_recommend": fb.get("recommend", ""), "comment": fb.get("comment", ""),
                    "flagged": integrity.verdict(integrity.load(r["integrity_json"]))["flagged"]})
    return out


def feedback_summary():
    rows = feedback_rows()
    rated = [r for r in rows if r["useful_1_to_5"]]
    tags = {}
    for r in rated:
        for t in filter(None, r["tags"].split("; ")):
            tags[t] = tags.get(t, 0) + 1
    avg = lambda xs: round(sum(xs) / len(xs), 1) if xs else None
    return {"responses": len(rated),
            "usefulness_counts": {str(n): sum(1 for r in rated if r["useful_1_to_5"] == n) for n in range(1, 6)},
            "average_usefulness": avg([r["useful_1_to_5"] for r in rated]),
            "average_confidence_before_pct": avg([r["confidence_before_pct"] for r in rows if r["confidence_before_pct"] is not None]),
            "average_confidence_after_pct": avg([r["confidence_after_pct"] for r in rated if r["confidence_after_pct"] is not None]),
            "average_score": avg([r["score"] for r in rows]),
            "tags": sorted(tags.items(), key=lambda kv: -kv[1])}


def insights(since=None, until=None):
    """Everything the Impact page draws, as anonymous totals: no names, emails, answers or comments.
    since / until (naive UTC datetimes) limit it to sessions started inside that window, for example the last 3 hours."""
    where, args = _window_sql(since, until)
    with get_conn() as conn:
        rows = conn.execute("SELECT s.user_id, s.upload_id, s.topic, s.confidence, s.time_limit, s.created_at, s.result_json, s.feedback_json, s.integrity_json, u.filename "
                            "FROM sessions s JOIN uploads u ON u.id = s.upload_id WHERE s.result_json IS NOT NULL" + where + " ORDER BY s.id", args).fetchall()
        started = conn.execute("SELECT COUNT(*) AS n FROM sessions s WHERE 1=1" + where, args).fetchone()["n"]
    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    span_hours = ((until or now) - since).total_seconds() / 3600 if since is not None else None
    bucket = "hour" if span_hours is not None and span_hours <= 48 else "day"
    avg = lambda xs: round(sum(xs) / len(xs), 1) if xs else None
    hist = [0] * 10
    crit = {k: [] for k in ("accuracy", "completeness", "consistency", "clarity")}
    useful, before, actual_pred, after = [], [], [], []
    recommend = {"yes": 0, "maybe": 0, "no": 0}
    tags, badges, days, groups = {}, {}, {}, {}
    calib = {"overconfident": 0, "close": 0, "underconfident": 0}
    flagged = timed = 0
    students, scores_all = set(), []
    for r in rows:
        try:
            score = json.loads(r["result_json"])["score"]
            overall = score["overall"]
        except (KeyError, TypeError, ValueError):
            continue
        students.add(r["user_id"])
        stamp = str(r["created_at"] or "")
        key = (stamp[:13] + ":00:00" if bucket == "hour" else stamp[:10] + " 00:00:00") if len(stamp) >= 13 else ""
        if key:
            days[key] = days.get(key, 0) + 1
        is_flagged = integrity.verdict(integrity.load(r["integrity_json"]))["flagged"]
        b = integrity.badge(overall, is_flagged)
        if b:
            badges[b["name"]] = badges.get(b["name"], 0) + 1
        if is_flagged:
            flagged += 1
            continue
        hist[min(9, overall // 10)] += 1
        scores_all.append(overall)
        for k in crit:
            try:
                crit[k].append(score["scores"][k]["score"])
            except (KeyError, TypeError):
                pass
        if r["time_limit"]:
            timed += 1
        if r["confidence"] is not None:
            before.append(r["confidence"] * 10); actual_pred.append(overall)
            gap = r["confidence"] * 10 - overall
            calib["overconfident" if gap >= 15 else "underconfident" if gap <= -15 else "close"] += 1
        try:
            fb = json.loads(r["feedback_json"]) if r["feedback_json"] else {}
        except ValueError:
            fb = {}
        if fb.get("useful"): useful.append(fb["useful"])
        if fb.get("confidence_after") is not None: after.append(fb["confidence_after"] * 10)
        if fb.get("recommend") in recommend: recommend[fb["recommend"]] += 1
        for t in fb.get("tags") or []:
            tags[t] = tags.get(t, 0) + 1
        groups.setdefault((r["user_id"], r["filename"], r["topic"]), []).append(overall)
    pairs = [{"first": g[0], "last": g[-1]} for g in groups.values() if len(g) >= 2]
    gains = [p["last"] - p["first"] for p in pairs]
    sessions = sum(hist)
    return {
        "started": started, "sessions": sessions, "flagged": flagged, "students": len(students), "timed_sessions": timed,
        "average_score": avg(scores_all),
        "score_histogram": hist,
        "criteria_average": {k: avg(v) for k, v in crit.items()},
        "usefulness_counts": [sum(1 for x in useful if x == n) for n in range(1, 6)], "average_usefulness": avg(useful), "ratings": len(useful),
        "recommend": recommend,
        "tags": sorted(tags.items(), key=lambda kv: -kv[1])[:12],
        "confidence": {"rated": len(before), "average_before": avg(before), "average_actual": avg(actual_pred), "average_after": avg(after), **calib},
        "retry": {"topics": len(pairs), "improved": sum(1 for x in gains if x > 0), "average_gain": avg(gains), "pairs": pairs[:40]},
        "badges": badges,
        "bucket": bucket,
        "per_bucket": [[k.replace(" ", "T") + "Z", n] for k, n in sorted(days.items())[-48:]],
        "window": {"since": since.isoformat() + "Z" if since else None, "until": until.isoformat() + "Z" if until else None},
    }
