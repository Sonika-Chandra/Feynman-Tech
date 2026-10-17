"""
Backend server (P3). Run from the repo root:   python backend/app.py
Endpoints are documented in docs/api.md.
Set USE_FAKE_AI=1 in .env to run without calling Gemini (no quota used).
"""
import json
import os
import sys
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)   # so `from ai import ai_module` works
sys.path.insert(0, HERE)   # so `import database` works

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request
from flask_cors import CORS
from werkzeug.exceptions import HTTPException
from werkzeug.utils import secure_filename

load_dotenv(os.path.join(ROOT, ".env"))

import database as db
import material

USE_FAKE_AI = os.getenv("USE_FAKE_AI", "0") == "1"
if USE_FAKE_AI:
    import fake_ai as ai
    transcribe = ai.transcribe
else:
    from ai import ai_module as ai
    from transcribe import transcribe

UPLOAD_DIR = os.path.join(HERE, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
ALLOWED_EXTENSIONS = {".pdf", ".pptx", ".docx", ".txt", ".md", ".png", ".jpg", ".jpeg"}
MAX_UPLOAD_MB = 20
MAX_MATERIAL_CHARS = 30000

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024
CORS(app)   # lets the frontend (a different port) call this server
db.init_db()


def err(message, status):
    return jsonify({"error": message}), status


def get_session_or_404(session_id):
    session = db.get_session(session_id)
    return session


# ------------------------------------------------------------------ health
@app.get("/health")
def health():
    return jsonify({"status": "ok", "fake_ai": USE_FAKE_AI})


# ------------------------------------------------------------------ 1. upload
@app.post("/upload")
def upload():
    f = request.files.get("file")
    if not f or not f.filename:
        return err("No file received. Send it as the form field 'file'.", 400)
    ext = os.path.splitext(f.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return err(f"File type '{ext}' is not supported. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}.", 400)

    safe_name = secure_filename(f.filename) or f"upload{ext}"
    path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex[:8]}_{safe_name}")
    f.save(path)

    try:
        sections = material.load_sections(path)
    except material.ExtractionError as e:
        return err(str(e), 422)
    except Exception as e:  # noqa: BLE001
        app.logger.exception(e)
        return err(f"Could not read this file: {e}", 422)

    text = "\n\n".join(s["text"] for s in sections).strip()
    if len(text) < 50:
        return err("Could not find enough readable text in this file. Is it a scanned image?", 422)

    upload_id = db.create_upload(f.filename, text, sections)
    return jsonify({
        "upload_id": upload_id,
        "filename": f.filename,
        "topics": [s["title"] for s in sections],
        "characters": len(text),
    }), 201


# ------------------------------------------------------------------ 2. start session
@app.post("/session/start")
def session_start():
    data = request.get_json(silent=True) or {}
    try:
        upload_row = db.get_upload(int(data.get("upload_id")))
    except (TypeError, ValueError):
        return err("'upload_id' is required and must be a number.", 400)
    if not upload_row:
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

    session_id = db.create_session(upload_row["id"], topic, material_text[:MAX_MATERIAL_CHARS])
    return jsonify({
        "session_id": session_id,
        "topic": topic,
        "prompt_to_student": "Explain this topic in your own words, as if you were teaching a beginner.",
    }), 201


# ------------------------------------------------------------------ 3. submit answer
@app.post("/session/answer")
def session_answer():
    body = request.get_json(silent=True) or {}
    session_id = body.get("session_id") or request.form.get("session_id")
    reply = (body.get("text") or request.form.get("text") or "").strip()
    audio = request.files.get("audio")

    try:
        session = db.get_session(int(session_id))
    except (TypeError, ValueError):
        return err("'session_id' is required and must be a number.", 400)
    if not session:
        return err("Unknown session_id.", 404)
    if session["status"] == "finished":
        return err(f"This session is finished. Call GET /session/{session['id']}/result.", 409)

    if audio and not reply:
        try:
            reply = transcribe(audio.read(), audio.mimetype)
        except Exception as e:  # noqa: BLE001
            app.logger.exception(e)
            return err(f"Could not transcribe the audio: {e}. You can send the answer as text instead.", 502)
    if not reply:
        return err("Send the answer as 'text', or record it and send the file as 'audio'.", 400)

    history = db.get_messages(session["id"])
    try:
        out = ai.next_question(session["material_text"], history, reply)
    except Exception as e:  # noqa: BLE001
        app.logger.exception(e)
        return err(f"The AI service failed: {e}", 502)

    pairs = [("student", reply)]
    if not out["should_stop"]:
        pairs.append(("ai", out["next_question"]))
    db.add_messages(session["id"], pairs)
    if out["should_stop"]:
        db.set_status(session["id"], "finished")

    return jsonify({**out, "transcript": reply, "session_status": "finished" if out["should_stop"] else "active"})


# ------------------------------------------------------------------ end early
@app.post("/session/<int:session_id>/finish")
def session_finish(session_id):
    if not db.get_session(session_id):
        return err("Unknown session_id.", 404)
    db.set_status(session_id, "finished")
    return jsonify({"session_id": session_id, "session_status": "finished"})


# ------------------------------------------------------------------ 4. result
@app.get("/session/<int:session_id>/result")
def session_result(session_id):
    session = db.get_session(session_id)
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
            package = ai.full_package(session["material_text"], history, language=language)
    except Exception as e:  # noqa: BLE001
        app.logger.exception(e)
        return err(f"The AI service failed: {e}", 502)

    db.save_result(session_id, package)
    db.set_status(session_id, "finished")
    return jsonify(package)


# ------------------------------------------------------------------ 5. report
@app.get("/session/<int:session_id>/report")
def session_report(session_id):
    if not db.get_session(session_id):
        return err("Unknown session_id.", 404)
    cached = db.get_result(session_id)
    if not cached or not cached.get("report_markdown"):
        return err(f"No report yet. Call GET /session/{session_id}/result first.", 404)
    headers = {}
    if request.args.get("download") == "1":
        headers["Content-Disposition"] = f'attachment; filename="mistake-report-{session_id}.md"'
    return Response(cached["report_markdown"], mimetype="text/markdown", headers=headers)


# ------------------------------------------------------------------ session info
@app.get("/session/<int:session_id>")
def session_info(session_id):
    session = db.get_session(session_id)
    if not session:
        return err("Unknown session_id.", 404)
    return jsonify({
        "session_id": session_id,
        "topic": session["topic"],
        "status": session["status"],
        "messages": db.get_messages(session_id),
    })


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
