"""
Backend server (P3). Run from the repo root:   python backend/app.py
Endpoints are documented in docs/api.md. Every endpoint except /, /health and /auth/register|login needs a login token.
Set USE_FAKE_AI=1 in .env to run without calling Gemini (no quota used).
"""
import base64
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
CORS(app)   # lets the frontend (a different port) call this server
db.init_db()
print("[ai]", "FAKE AI (no Gemini requests)" if USE_FAKE_AI else ai.status())


def err(message, status):
    return jsonify({"error": message}), status


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
    return jsonify({"status": "ok", "fake_ai": USE_FAKE_AI, **ai.status()})


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
        app.logger.exception(e)
        return err(f"Could not read this file: {e}", 422)

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
    try:
        wav = ai.speak_wav(text, str(data.get("voice") or "Aoede"))
    except Exception as e:  # noqa: BLE001
        return err(str(e), 503)
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
        first = ai.opening_question(material_text)
    except Exception as e:  # noqa: BLE001
        app.logger.exception(e)
        return err(f"The AI service failed: {e}", 502)

    session_id = db.create_session(upload_row["id"], topic, material_text, g.user["id"])
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

    if audio and not reply:
        try:
            reply = transcribe(audio.read(), audio.mimetype, context=session["material_text"])
        except Exception as e:  # noqa: BLE001
            app.logger.exception(e)
            return err(f"Could not transcribe the audio: {e}. You can send the answer as text instead.", 502)

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
            app.logger.exception(e)
            return err(f"The AI service failed while reading the whiteboard: {e}", 502)
        ext = ".png" if "png" in drawing_mime else ".jpg"
        image_path = os.path.join(DRAWING_DIR, uuid.uuid4().hex + ext)
        with open(image_path, "wb") as fh:
            fh.write(drawing_bytes)
        stored_reply = (reply + "\n\n" if reply else "") + "[Whiteboard drawing]\n" + description
    else:
        stored_reply = reply

    try:
        out = ai.next_question(session["material_text"], history, stored_reply)
    except Exception as e:  # noqa: BLE001
        app.logger.exception(e)
        return err(f"The AI service failed: {e}", 502)

    out["diagram_svg"] = safe_svg(out.get("diagram_svg"))
    out["needs_whiteboard"] = bool(out.get("needs_whiteboard")) or bool(out["diagram_svg"])
    items = [("student", stored_reply, {"image_path": image_path})]
    if not out["should_stop"]:
        items.append(("ai", out["next_question"], {"needs_whiteboard": out["needs_whiteboard"], "diagram_svg": out["diagram_svg"]}))
    db.add_messages(session["id"], items)
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
    if cached and (mode == "score" or cached.get("report_markdown")):
        return jsonify(cached)

    history = db.get_messages(session_id)
    if not any(m["role"] == "student" for m in history):
        return err("No answers yet. Submit at least one answer first.", 400)

    try:
        if mode == "score":
            package = {"score": ai.final_score(session["material_text"], history),
                       "fact_check": None, "report_markdown": None, "notes": None}
        else:
            package = ai.full_package(session["material_text"], history, language=language,
                                      score=(cached or {}).get("score"))
    except Exception as e:  # noqa: BLE001
        app.logger.exception(e)
        return err(f"The AI service failed: {e}", 502)

    db.save_result(session_id, package)
    db.set_status(session_id, "finished")
    return jsonify(package)


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
    if kind not in ("gaps", "full"):
        return err("kind must be 'gaps' or 'full'.", 400)
    result = db.get_result(session_id)
    if not result or not result.get("score"):
        return err("No result yet. Finish the session and open the report first.", 404)
    if kind == "gaps":
        data = export_docx.build_gap_report(session, g.user, result)
        name = f"gap-report-{session_id}.docx"
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
