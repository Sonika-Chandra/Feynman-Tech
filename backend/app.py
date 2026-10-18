"""
Backend server (P3). Run from the repo root:   python backend/app.py
Endpoints are documented in docs/api.md. Every endpoint except /, /health and /auth/register|login needs a login token.
Set USE_FAKE_AI=1 in .env to run without calling Gemini (no quota used).
"""
import base64
import datetime
import functools
import json
import os
import re
import secrets
import sys
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)   # so `from ai import ai_module` works
sys.path.insert(0, HERE)   # so `import database` works

from dotenv import load_dotenv
from flask import Flask, Response, g, jsonify, request, send_from_directory
from flask_cors import CORS
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

load_dotenv(os.path.join(ROOT, ".env"))

import database as db
import export_docx
import integrity
import material
from svg_clean import safe_svg

USE_FAKE_AI = os.getenv("USE_FAKE_AI", "0") == "1"
if USE_FAKE_AI:
    import fake_ai as ai
else:
    from ai import ai_module as ai
from transcribe import transcribe   # honours USE_FAKE_AI by itself

UPLOAD_DIR = os.path.join(HERE, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
ALLOWED_EXTENSIONS = {".pdf", ".pptx", ".docx", ".txt", ".md", ".png", ".jpg", ".jpeg"}
MAX_UPLOAD_MB = 20
MAX_MATERIAL_CHARS = 30000
TOTAL_QUESTIONS = 5
DRAWING_DIR = os.path.join(UPLOAD_DIR, "drawings")
os.makedirs(DRAWING_DIR, exist_ok=True)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

FRONTEND_DIR = os.path.join(ROOT, "frontend")

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024
CORS(app, allow_headers=["Content-Type", "Authorization", "X-Gemini-Key"])   # lets the frontend (a different port) call this server
db.init_db()
print("[ai]", "FAKE AI (no Gemini requests)" if USE_FAKE_AI else ai.status())


# ------------------------------------------------------------------ public-demo protection
PUBLIC = os.getenv("PUBLIC", "0") == "1"                       # set on the hosted site
DAILY_AI_LIMIT = int(os.getenv("DAILY_AI_LIMIT", "0") or 0)    # AI requests per user per day (0 = unlimited)
_spent = {}


KEY_RE = re.compile(r"^[\x21-\x7E]{20,300}$")      # any printable key without spaces (new Google keys can contain dots)


@app.before_request
def pick_gemini_key():
    """A visitor's own Gemini key (header X-Gemini-Key) is used for their requests only. It is never stored or logged."""
    key = (request.headers.get("X-Gemini-Key") or "").strip()
    g.user_key = key if KEY_RE.match(key) else ""
    ai.use_key(g.user_key)
    needs_ai = request.method != "OPTIONS" and (request.path in ("/upload", "/session/start", "/session/answer", "/tts", "/key/check")
                                                or (request.path.startswith("/session/") and request.path.endswith("/result")))
    if needs_ai and not USE_FAKE_AI and not g.user_key and not ai.server_key():
        return jsonify({"error": "This site needs a Gemini API key. Click the key button at the top and paste yours (free at aistudio.google.com/apikey).", "code": "no_key"}), 428


def over_budget(cost=1):
    """True (and counts nothing) when this user has used up today's AI requests; otherwise counts `cost` and returns False."""
    if getattr(g, "user_key", ""):
        return False          # they are spending their own quota, not ours
    if not DAILY_AI_LIMIT:
        return False
    key = (g.user["id"], datetime.date.today().isoformat())
    used = _spent.get(key, 0)
    if used + cost > DAILY_AI_LIMIT:
        return True
    _spent[key] = used + cost
    return False


LIMIT_MESSAGE = ("You have reached today's limit for this public demo, to keep the free AI quota fair for everyone. "
                 "Add your own free Gemini key (the key button at the top) to carry on right now, or come back tomorrow.")


def err(message, status, code=None):
    body = {"error": message}
    if code:
        body["code"] = code
    return jsonify(body), status


def ai_fail(e):
    """A Gemini failure as a short, friendly answer with a code the page understands (quota, bad_key, busy, network, ...)."""
    app.logger.exception(e)
    code, message, status = ai.friendly_error(e)
    return err(message, status, code)


# ------------------------------------------------------------------ the web page
@app.get("/")
def home():
    if os.path.exists(os.path.join(FRONTEND_DIR, "index.html")):
        return send_from_directory(FRONTEND_DIR, "index.html")
    return jsonify({"message": "Backend is running, but the frontend/ folder was not found."})


# ------------------------------------------------------------------ login
def login_required(view):
    """Requests must send the header  Authorization: Bearer <token>  from /auth/login or /auth/register."""
    @functools.wraps(view)
    def wrapper(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        token = header[7:].strip() if header.lower().startswith("bearer ") else ""
        user = db.get_user_by_token(token) if token else None
        if not user:
            return err("Please log in first.", 401)
        g.user = user
        g.token = token
        return view(*args, **kwargs)
    return wrapper


def public_user(user):
    return {"id": user["id"], "name": user["name"], "email": user["email"]}


def issue_token(user_id):
    token = secrets.token_urlsafe(32)      # never expires; it is deleted only by /auth/logout
    db.create_token(user_id, token)
    return token


@app.post("/auth/register")
def auth_register():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    if not name:
        return err("Please enter your name.", 400)
    if not EMAIL_RE.match(email):
        return err("Please enter a valid email address.", 400)
    if len(password) < 6:
        return err("Password must be at least 6 characters.", 400)
    if db.get_user_by_email(email):
        return err("An account with this email already exists. Log in instead.", 409)
    user_id = db.create_user(name, email, generate_password_hash(password))
    return jsonify({"token": issue_token(user_id), "user": public_user(db.get_user(user_id))}), 201


@app.post("/auth/login")
def auth_login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    user = db.get_user_by_email(email)
    if not user or not check_password_hash(user["password_hash"], data.get("password") or ""):
        return err("Wrong email or password.", 401)
    return jsonify({"token": issue_token(user["id"]), "user": public_user(user)})


@app.get("/auth/me")
@login_required
def auth_me():
    return jsonify({"user": public_user(g.user)})


@app.post("/auth/logout")
@login_required
def auth_logout():
    db.delete_token(g.token)
    return jsonify({"ok": True})


@app.get("/sessions")
@login_required
def sessions_list():
    return jsonify({"sessions": db.list_sessions(g.user["id"])})


def own_session(session_id):
    """The session if it exists and belongs to the logged-in user, else None."""
    session = db.get_session(session_id)
    if session and session["user_id"] == g.user["id"]:
        return session
    return None


# ------------------------------------------------------------------ health
@app.get("/health")
def health():
    info = ai.status()
    if PUBLIC or getattr(g, "user_key", ""):
        info = {**info, "key_ending": None}
    own = bool(getattr(g, "user_key", ""))
    out = {"status": "ok", "fake_ai": USE_FAKE_AI, "public": PUBLIC, "server_key": bool(ai.server_key()) or USE_FAKE_AI,
           "using_own_key": own, **info}
    if own:
        out["requests"] = ai.usage(g.user_key)      # show THEIR count, not the server's
    return jsonify(out)


@app.post("/key/check")
def key_check():
    """Proves the visitor's key works with one tiny request (this request is made with their key)."""
    if not getattr(g, "user_key", "") and not USE_FAKE_AI:
        return err("Paste a Gemini API key first.", 400)
    try:
        result = ai.check_key()
    except Exception as e:  # noqa: BLE001
        return ai_fail(e)
    return jsonify({**result, "requests": ai.usage(g.user_key)})


# ------------------------------------------------------------------ 1. upload
def better_headings(sections):
    """When the file had no real headings, name the parts well: with the AI if possible, else from the first sentence."""
    from ingestion import topics as _t
    if len(sections) < 2 or not any(_t.is_generic(x["title"]) and not x["title"].lower().startswith("introduction") for x in sections):
        return sections
    if not USE_FAKE_AI:
        try:
            titles = ai.better_titles(sections)
            return _t.finalize([{"title": t, "text": x["text"]} for t, x in zip(titles, sections)])
        except Exception as e:  # noqa: BLE001
            app.logger.warning("AI headings skipped: %s", e)
    return _t.retitle_generic(sections)


@app.post("/upload")
@login_required
def upload():
    f = request.files.get("file")
    if not f or not f.filename:
        return err("No file received. Send it as the form field 'file'.", 400)
    ext = os.path.splitext(f.filename)[1].lower()
    if ext in (".doc", ".ppt"):
        return err(f"Old {ext} files are not supported. Save it as {ext}x and upload it again.", 400)
    if ext not in ALLOWED_EXTENSIONS:
        return err(f"File type '{ext}' is not supported. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}.", 400)

    safe_name = secure_filename(f.filename) or f"upload{ext}"
    folder = os.path.join(UPLOAD_DIR, uuid.uuid4().hex[:8])      # one folder per upload keeps the real file name
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, safe_name)
    f.save(path)

    try:
        sections = material.load_sections(path)
    except material.ExtractionError as e:
        return err(str(e), 422)
    except Exception as e:  # noqa: BLE001
        if ai.friendly_error(e)[0] != "unknown":
            return ai_fail(e)               # the AI part failed (image or scan reading): quota, key, busy ...
        app.logger.exception(e)
        return err("Could not read this file. Try another copy, or save it as PDF, Word or text.", 422)

    sections = better_headings(sections)
    text = "\n\n".join(s["text"] for s in sections).strip()
    if len(text) < 50:
        return err("Could not find enough readable text in this file. Is it a scanned image?", 422)

    upload_id = db.create_upload(f.filename, text, sections, g.user["id"])
    return jsonify({
        "upload_id": upload_id,
        "filename": f.filename,
        "topics": [s["title"] for s in sections],
        "sections": [{"title": s["title"], "preview": s["text"][:500]} for s in sections],
        "characters": len(text),
    }), 201


# ------------------------------------------------------------------ read a question aloud (AI voice)
@app.post("/tts")
@login_required
def tts():
    data = request.get_json(silent=True) or {}
    text = str(data.get("text") or "").strip()
    if not text:
        return err("Send {\"text\": \"...\"}.", 400)
    if over_budget(1):
        return err(LIMIT_MESSAGE, 429, "quota")
    try:
        wav = ai.speak_wav(text, str(data.get("voice") or "Aoede"))
    except Exception as e:  # noqa: BLE001
        app.logger.warning("tts failed: %s", e)
        code, message, _ = ai.friendly_error(e)
        return err(message, 503, code)
    return Response(wav, mimetype="audio/wav")


# ------------------------------------------------------------------ 2. start session (the AI speaks first)
@app.post("/session/start")
@login_required
def session_start():
    data = request.get_json(silent=True) or {}
    try:
        upload_row = db.get_upload(int(data.get("upload_id")))
    except (TypeError, ValueError):
        return err("'upload_id' is required and must be a number.", 400)
    if not upload_row or upload_row["user_id"] != g.user["id"]:
        return err("Unknown upload_id.", 404)

    topic = (data.get("topic") or "").strip()
    if topic:
        matches = [s for s in json.loads(upload_row["sections_json"]) if s["title"] == topic]
        if not matches:
            return err(f"Topic '{topic}' not found in this upload.", 400)
        material_text = matches[0]["text"]
    else:
        topic = "Whole document"
        material_text = upload_row["text"]
    material_text = material_text[:MAX_MATERIAL_CHARS]

    try:
        time_limit = max(0, min(int(data.get("time_limit") or 0), 600))
    except (TypeError, ValueError):
        time_limit = 0
    try:
        confidence = data.get("confidence")
        confidence = None if confidence in (None, "") else max(0, min(int(confidence), 10))
    except (TypeError, ValueError):
        confidence = None
    if over_budget(1):
        return err(LIMIT_MESSAGE, 429, "quota")
    try:
        first = ai.opening_question(material_text, time_limit)
    except Exception as e:  # noqa: BLE001
        return ai_fail(e)

    session_id = db.create_session(upload_row["id"], topic, material_text, g.user["id"], time_limit, confidence)
    diagram = safe_svg(first.get("diagram_svg"))
    db.add_messages(session_id, [("ai", first["next_question"], {"needs_whiteboard": first["needs_whiteboard"] or bool(diagram), "diagram_svg": diagram})])
    return jsonify({
        "session_id": session_id,
        "topic": topic,
        "next_question": first["next_question"],
        "needs_whiteboard": first["needs_whiteboard"] or bool(diagram),
        "diagram_svg": diagram,
        "round": 1,
        "total_rounds": TOTAL_QUESTIONS,
    }), 201


# ------------------------------------------------------------------ 3. submit answer (text, voice and/or whiteboard drawing)
def read_drawing():
    """Returns (bytes, mime) of a drawing sent as a file 'drawing' or as a data URL in the JSON field 'drawing'; else (None, None)."""
    f = request.files.get("drawing")
    if f:
        return f.read(), (f.mimetype or "image/png")
    body = request.get_json(silent=True) or {}
    data_url = body.get("drawing")
    if isinstance(data_url, str) and data_url.startswith("data:") and "," in data_url:
        head, b64 = data_url.split(",", 1)
        mime = head[5:].split(";")[0] or "image/png"
        return base64.b64decode(b64), mime
    return None, None


@app.post("/session/answer")
@login_required
def session_answer():
    body = request.get_json(silent=True) or {}
    session_id = body.get("session_id") or request.form.get("session_id")
    reply = (body.get("text") or request.form.get("text") or "").strip()
    audio = request.files.get("audio")

    try:
        session = own_session(int(session_id))
    except (TypeError, ValueError):
        return err("'session_id' is required and must be a number.", 400)
    if not session:
        return err("Unknown session_id.", 404)
    if session["status"] == "finished":
        return err(f"This session is finished. Call GET /session/{session['id']}/result.", 409)

    cost = 1 + (1 if audio and not reply else 0) + (1 if (request.files.get("drawing") or body.get("drawing")) else 0)
    if over_budget(cost):
        return err(LIMIT_MESSAGE, 429, "quota")

    if audio and not reply:
        try:
            reply = transcribe(audio.read(), audio.mimetype, context=session["material_text"])
        except Exception as e:  # noqa: BLE001
            return ai_fail(e)

    drawing_bytes, drawing_mime = None, None
    try:
        drawing_bytes, drawing_mime = read_drawing()
    except Exception:  # noqa: BLE001
        return err("The drawing could not be read. Try again.", 400)
    if not reply and not drawing_bytes:
        return err("Send the answer as 'text', record it and send the file as 'audio', or draw on the whiteboard.", 400)

    history = db.get_messages(session["id"])
    image_path = None
    if drawing_bytes:
        question = next((m["text"] for m in reversed(history) if m["role"] == "ai"), "")
        try:
            description = ai.describe_drawing(question, drawing_bytes, drawing_mime)
        except Exception as e:  # noqa: BLE001
            return ai_fail(e)
        ext = ".png" if "png" in drawing_mime else ".jpg"
        image_path = os.path.join(DRAWING_DIR, uuid.uuid4().hex + ext)
        with open(image_path, "wb") as fh:
            fh.write(drawing_bytes)
        stored_reply = (reply + "\n\n" if reply else "") + "[Whiteboard drawing]\n" + description
    else:
        stored_reply = reply

    # The answer is saved FIRST. If the student ends the session while the AI is still writing the next question,
    # the report still counts this answer, and the late question is simply dropped.
    student_id = db.add_messages(session["id"], [("student", stored_reply, {"image_path": image_path})])[0]
    try:
        out = ai.next_question(session["material_text"], history, stored_reply, session["time_limit"] or 0)
    except Exception as e:  # noqa: BLE001
        db.delete_message(student_id)                 # nothing was asked, so the same answer can be sent again after a retry
        return ai_fail(e)

    out["diagram_svg"] = safe_svg(out.get("diagram_svg"))
    out["needs_whiteboard"] = bool(out.get("needs_whiteboard")) or bool(out["diagram_svg"])
    state = integrity.add_answer(integrity.load(session["integrity_json"]), reply, session["material_text"],
                                 request.form.get("paste_attempts") or body.get("paste_attempts"),
                                 request.form.get("tab_switches") or body.get("tab_switches"))
    db.save_integrity(session["id"], state)
    ended_meanwhile = (db.get_session(session["id"]) or {"status": "active"})["status"] == "finished"
    if ended_meanwhile:
        out["should_stop"] = True                     # the student already ended the session: no further question
    elif not out["should_stop"]:
        db.add_messages(session["id"], [("ai", out["next_question"], {"needs_whiteboard": out["needs_whiteboard"], "diagram_svg": out["diagram_svg"]})])
    if out["should_stop"]:
        db.set_status(session["id"], "finished")

    return jsonify({**out, "transcript": reply, "total_rounds": TOTAL_QUESTIONS,
                    "drawing_description": stored_reply.split("[Whiteboard drawing]\n", 1)[1] if drawing_bytes else None,
                    "session_status": "finished" if out["should_stop"] else "active"})


# ------------------------------------------------------------------ end early
@app.post("/session/<int:session_id>/finish")
@login_required
def session_finish(session_id):
    if not own_session(session_id):
        return err("Unknown session_id.", 404)
    db.set_status(session_id, "finished")
    return jsonify({"session_id": session_id, "session_status": "finished"})


def with_integrity(package, session):
    """Adds the honesty verdict and the badge to a result without changing what is stored."""
    session = db.get_session(session["id"])
    verdict = integrity.verdict(integrity.load(session["integrity_json"]))
    overall = ((package or {}).get("score") or {}).get("overall")
    try:
        feedback = json.loads(session["feedback_json"]) if session["feedback_json"] else None
    except ValueError:
        feedback = None
    return {**package, "integrity": verdict, "badge": integrity.badge(overall, verdict["flagged"]),
            "confidence": session["confidence"], "feedback": feedback}


@app.post("/session/<int:session_id>/feedback")
@login_required
def session_feedback(session_id):
    if not own_session(session_id):
        return err("Unknown session_id.", 404)
    d = request.get_json(silent=True) or {}
    try:
        ca = d.get("confidence_after")
        fb = {"useful": max(1, min(int(d.get("useful")), 5)),
              "confidence_after": None if ca is None else max(0, min(int(ca), 10)),
              "recommend": d.get("recommend") if d.get("recommend") in ("yes", "maybe", "no") else "",
              "comment": str(d.get("comment") or "")[:500],
              "tags": [str(t)[:40] for t in (d.get("tags") or []) if isinstance(t, str)][:12]}
    except (TypeError, ValueError):
        return err("'useful' (1 to 5) is required; 'confidence_after' (0 to 10) is optional.", 400)
    db.save_feedback(session_id, fb)
    return jsonify({"ok": True, "feedback": fb})


FEEDBACK_KEY = os.getenv("FEEDBACK_KEY", "")


@app.get("/feedback/summary")
def feedback_summary():
    """Anonymous totals of the feedback form: counts of ratings and of the tags students tapped. No comments."""
    return jsonify(db.feedback_summary())


def time_window():
    """Optional time window from the query string, as naive UTC datetimes (the database stores UTC):
       ?hours=3                               the last 3 hours
       ?since=2026-10-18T10:00:00Z&until=...   an exact window (ISO 8601; a missing zone means UTC)"""
    def parse(v):
        try:
            d = datetime.datetime.fromisoformat(v.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
        return d.astimezone(datetime.timezone.utc).replace(tzinfo=None) if d.tzinfo else d
    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    since = until = None
    hours = request.args.get("hours", type=float)
    if hours and hours > 0:
        since = now - datetime.timedelta(hours=min(hours, 24 * 366))
    if request.args.get("since"):
        since = parse(request.args["since"]) or since
    if request.args.get("until"):
        until = parse(request.args["until"])
    return since, until


@app.get("/feedback/export.csv")
def feedback_export():
    """All feedback, one row per session, for the team to compile. Locally it is open; on a public site it needs ?key=FEEDBACK_KEY."""
    allowed = (FEEDBACK_KEY and request.args.get("key") == FEEDBACK_KEY) or (not PUBLIC and not FEEDBACK_KEY)
    if not allowed:
        return err("Not allowed. Set FEEDBACK_KEY on the server and open /feedback/export.csv?key=YOUR_KEY.", 403)
    import csv, io
    since, until = time_window()
    rows = db.feedback_rows(since, until)
    buf = io.StringIO()
    cols = ["session_id", "date", "file", "topic", "confidence_before_pct", "score", "confidence_after_pct", "useful_1_to_5", "would_recommend", "tags", "comment", "flagged"]
    w = csv.DictWriter(buf, fieldnames=cols)
    w.writeheader()
    w.writerows(rows)
    return Response("\ufeff" + buf.getvalue(), mimetype="text/csv", headers={"Content-Disposition": 'attachment; filename="vocalis-feedback.csv"'})


@app.get("/insights")
def insights():
    """Anonymous totals for the Impact page: score spread, ratings, confidence vs real score, retry gains, badges. No names, answers or comments."""
    since, until = time_window()
    return jsonify(db.insights(since, until))


@app.get("/stats")
def stats():
    """Anonymous totals (no names or answers) for the evidence slide."""
    return jsonify(db.stats())


@app.get("/profile")
@login_required
def profile():
    rows = [s for s in reversed(db.list_sessions(g.user["id"])) if s["overall"] is not None]
    return jsonify(integrity.profile(rows))


# ------------------------------------------------------------------ progress across retries
@app.get("/session/<int:session_id>/progress")
@login_required
def session_progress(session_id):
    session = own_session(session_id)
    if not session:
        return err("Unknown session_id.", 404)
    up = db.get_upload(session["upload_id"])
    return jsonify({"attempts": db.attempts_for(g.user["id"], up["filename"], session["topic"])})


# ------------------------------------------------------------------ 4. result
@app.get("/session/<int:session_id>/result")
@login_required
def session_result(session_id):
    session = own_session(session_id)
    if not session:
        return err("Unknown session_id.", 404)

    mode = request.args.get("mode", "full")          # "full" or "score" (score only = 1 AI call)
    language = request.args.get("lang", "Kannada")

    cached = db.get_result(session_id)
    need_report = not (cached or {}).get("report_markdown")
    if cached and cached.get("score") and (mode == "score" or not need_report):
        return jsonify(with_integrity(cached, session))          # everything asked for is already saved: no AI request

    history = db.get_messages(session_id)
    if not any(m["role"] == "student" for m in history):
        return err("No answers yet. Submit at least one answer first.", 400)

    cost = 1 if mode == "score" else (1 if (cached and cached.get("score")) else 2)
    if over_budget(cost):
        return err(LIMIT_MESSAGE, 429, "quota")
    try:
        if mode == "score":
            package = {"score": ai.final_score(session["material_text"], history),
                       "report_markdown": None, "notes": None}
        else:
            package = ai.full_package(session["material_text"], history, language=language, score=(cached or {}).get("score"))
    except Exception as e:  # noqa: BLE001
        return ai_fail(e)

    db.save_result(session_id, package)
    db.set_status(session_id, "finished")
    return jsonify(with_integrity(package, session))


# ------------------------------------------------------------------ 5. report
@app.get("/session/<int:session_id>/report")
@login_required
def session_report(session_id):
    if not own_session(session_id):
        return err("Unknown session_id.", 404)
    cached = db.get_result(session_id)
    if not cached or not cached.get("report_markdown"):
        return err(f"No report yet. Call GET /session/{session_id}/result first.", 404)
    headers = {}
    if request.args.get("download") == "1":
        headers["Content-Disposition"] = f'attachment; filename="mistake-report-{session_id}.md"'
    return Response(cached["report_markdown"], mimetype="text/markdown", headers=headers)


# ------------------------------------------------------------------ Word downloads
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@app.get("/session/<int:session_id>/export")
@login_required
def session_export(session_id):
    """?kind=gaps -> gap report (.docx), ?kind=full -> full session report (.docx). Needs the result to exist."""
    session = own_session(session_id)
    if not session:
        return err("Unknown session_id.", 404)
    kind = request.args.get("kind", "gaps")
    if kind not in ("gaps", "notes", "full"):
        return err("kind must be 'gaps', 'notes' or 'full'.", 400)
    result = db.get_result(session_id)
    if not result or not result.get("score"):
        return err("No result yet. Finish the session and open the report first.", 404)
    if kind == "gaps":
        data = export_docx.build_gap_report(session, g.user, result)
        name = f"gap-report-{session_id}.docx"
    elif kind == "notes":
        if not (result.get("notes") or {}).get("notes"):
            return err("The revision notes are not ready yet. Open the report page first.", 404)
        data = export_docx.build_notes_report(session, g.user, result)
        name = f"revision-notes-{session_id}.docx"
    else:
        messages = db.get_messages_full(session_id)

        def drawing_path(m):
            row = db.get_message(m["id"]) if m.get("id") else None
            return row["image_path"] if row and row["image_path"] else None
        data = export_docx.build_full_report(session, g.user, result, messages, drawing_path)
        name = f"full-report-{session_id}.docx"
    return Response(data, mimetype=DOCX_MIME, headers={"Content-Disposition": f'attachment; filename="{name}"'})


# ------------------------------------------------------------------ session info
@app.get("/session/<int:session_id>")
@login_required
def session_info(session_id):
    session = own_session(session_id)
    if not session:
        return err("Unknown session_id.", 404)
    messages = db.get_messages_full(session_id)
    return jsonify({
        "session_id": session_id,
        "topic": session["topic"],
        "status": session["status"],
        "total_rounds": TOTAL_QUESTIONS,
        "round": sum(1 for m in messages if m["role"] == "ai"),
        "messages": messages,
    })


@app.get("/message/<int:message_id>/drawing")
@login_required
def message_drawing(message_id):
    msg = db.get_message(message_id)
    if not msg or not msg["image_path"] or not own_session(msg["session_id"]):
        return err("No drawing found.", 404)
    folder, name = os.path.split(msg["image_path"])
    return send_from_directory(folder, name)


# ------------------------------------------------------------------ errors as JSON
@app.errorhandler(HTTPException)
def handle_http_error(e):
    return jsonify({"error": e.description}), e.code


@app.errorhandler(Exception)
def handle_any_error(e):
    app.logger.exception(e)
    return jsonify({"error": "Server error. Check the backend terminal for details."}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=True)
