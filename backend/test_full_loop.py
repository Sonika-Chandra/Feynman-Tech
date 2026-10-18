"""
The whole study loop through the REAL backend and the REAL ai_module, with only the Gemini client replaced by a counting stub (free, instant):
  upload -> 5 questions -> score -> report + notes -> Word reports -> gap report -> test on the gaps -> second report.
Proves that every feature works in one go and shows how many Gemini requests the loop costs.
    python backend/test_full_loop.py
"""
import io
import json
import os
import sys
import tempfile

os.environ["USE_FAKE_AI"] = "0"
os.environ["GEMINI_API_KEY"] = "test-key-not-real"
os.environ["DATABASE_PATH"] = os.path.join(tempfile.mkdtemp(), "loop.db")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

from ai import ai_module as ai  # noqa: E402

calls = []


class _R:
    def __init__(self, text):
        self.text = text; self.parsed = None; self.candidates = []


class _Models:
    def generate_content(self, model, contents, config):
        calls.append(getattr(getattr(config, "response_schema", None), "__name__", "text"))
        name = calls[-1]
        crit = {"score": 7, "justification": "Mostly right."}
        body = {
            "NextTurn": {"next_question": "Next question about the topic?", "needs_whiteboard": False, "diagram_svg": ""},
            "GradeResult": {"accuracy": crit, "completeness": {"score": 6, "justification": "Missed a step."}, "consistency": crit, "clarity": crit,
                            "mistakes": ["Swapped the order of the stages."], "summary": "Good start. Review the order."},
            "MistakeList": {"items": [{"concept_misunderstood": "The order of the two stages", "correct_explanation": "Light reactions come first.",
                                       "recommended_review": "Redraw the stages.", "what_student_said": "Said the Calvin cycle first.",
                                       "why_it_matters": "The second stage uses the first's products.", "practice_question": "Which stage comes first?"}],
                            "strengths": ["Clear overview"], "study_plan": ["Redraw the stages", "Explain it aloud"],
                            "question_feedback": [{"question": "Q1", "answer_summary": "Overview", "feedback": "Add the order."}],
                            "revision_notes": "## Stages\n- Light reactions first", "revision_notes_translated": "## ಹಂತಗಳು\n- ಬೆಳಕಿನ ಕ್ರಿಯೆ ಮೊದಲು"},
        }.get(name)
        return _R(json.dumps(body, ensure_ascii=False) if body is not None else
                  "- Where: study material\n- Statement: x\n- Concern: y\n- Confidence: low")


class _Client:
    models = _Models()


ai._client = _Client()
from app import app  # noqa: E402

failures = []


def check(name, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + name + (("  -> " + str(detail)) if not cond and detail else ""))
    if not cond:
        failures.append(name)


c = app.test_client()
tok = c.post("/auth/register", json={"name": "Loop", "email": "loop@example.com", "password": "secret1"}).get_json()["token"]
H = {"Authorization": "Bearer " + tok}
NOTES = ("Photosynthesis turns light energy into chemical energy in chloroplasts. The light reactions make ATP and NADPH and release oxygen. "
         "The Calvin cycle then uses ATP and NADPH to turn carbon dioxide into glucose.")


def run_session(upload_id, topic=None):
    s = c.post("/session/start", json={"upload_id": upload_id, "topic": topic}, headers=H).get_json()
    sid = s["session_id"]
    for i in range(5):
        r = c.post("/session/answer", json={"session_id": sid, "text": "My explanation number %d about the topic." % i}, headers=H).get_json()
    assert r["should_stop"] is True
    sc = c.get(f"/session/{sid}/result?mode=score", headers=H)
    full = c.get(f"/session/{sid}/result?lang=Kannada", headers=H)
    return sid, sc, full


up = c.post("/upload", data={"file": (io.BytesIO(NOTES.encode()), "photosynthesis.md")}, content_type="multipart/form-data", headers=H).get_json()
before = len(calls)
sid, sc, full = run_session(up["upload_id"])
cost1 = len(calls) - before
pkg = full.get_json()
check("score shows first", sc.status_code == 200 and sc.get_json()["score"]["overall"] > 0)
check("full result has score, report, notes, gaps", all(pkg.get(k) for k in ("score", "report_markdown", "notes", "gaps", "strengths", "study_plan", "question_feedback")), list(pkg))
check("notes are in Kannada from the same request as the report", pkg["notes"]["language"] == "Kannada" and "ಹಂತಗಳು" in pkg["notes"]["notes_translated"])
check("first session cost exactly 7 Gemini requests", cost1 == 7, cost1)

g = c.get(f"/session/{sid}/export?kind=gaps", headers=H)
f = c.get(f"/session/{sid}/export?kind=full", headers=H)
check("both Word reports download", g.status_code == 200 and f.status_code == 200 and g.data[:2] == b"PK" and f.data[:2] == b"PK")
md = c.get(f"/session/{sid}/report", headers=H).get_data(as_text=True)
check("gap report markdown has the fixed headings", "### Concept Misunderstood" in md)

# test on the gaps: upload the saved report (both formats), then run a second session on a gap
before2 = len(calls)
up2 = c.post("/upload", data={"file": (io.BytesIO(md.encode()), "gap-report.md")}, content_type="multipart/form-data", headers=H)
up3 = c.post("/upload", data={"file": (io.BytesIO(g.data), "gap-report.docx")}, content_type="multipart/form-data", headers=H)
check("gap report (.md) uploads again with no AI request", up2.status_code == 201 and len(calls) == before2, up2.get_data(as_text=True)[:200])
check("gap report (.docx) uploads again too", up3.status_code == 201 and any(t.startswith("Mistake 1") for t in up3.get_json()["topics"]))
topic = up2.get_json()["topics"][-1]
sid2, sc2, full2 = run_session(up2.get_json()["upload_id"], topic)
check("test-on-gaps session produces its own full report", full2.status_code == 200 and bool(full2.get_json().get("report_markdown")))
total = len(calls)
check("whole loop (session + gap re-test) = 14 requests, inside the free 20/day", total == 14, total)
health = c.get("/health").get_json()
check("/health shows the same request count the app displays", health.get("requests") == 14, health)

# ---- visitors bringing their own key
KEY = {"X-Gemini-Key": "AIzaTestKeyNotReal_1234567890abcd"}
h0 = c.get("/health", headers=KEY).get_json()
check("/health with a visitor key says so and shows THEIR count (0), not the server's", h0.get("using_own_key") is True and h0.get("requests") == 0, h0)
ck = c.post("/key/check", headers=KEY)
check("/key/check makes one request with their key", ck.status_code == 200 and ck.get_json().get("requests") == 1, ck.get_data(as_text=True)[:200])
check("their count is shown afterwards", c.get("/health", headers=KEY).get_json().get("requests") == 1)
check("the server's own count did not include the visitor's key", c.get("/health", headers=H).get_json().get("requests") == 15)
check("a malformed key is ignored, not used", c.get("/health", headers={"X-Gemini-Key": "bad key!"}).get_json().get("using_own_key") is False)
saved = os.environ.pop("GEMINI_API_KEY")
r428 = c.post("/session/start", json={"upload_id": 1}, headers=H)
check("no server key and no visitor key -> 428 asking for a key", r428.status_code == 428 and r428.get_json().get("code") == "no_key")
check("health says the site needs a key", c.get("/health").get_json().get("server_key") is False)
os.environ["GEMINI_API_KEY"] = saved
import app as _app
_app.DAILY_AI_LIMIT = 1
r = c.post("/session/start", json={"upload_id": up2.get_json()["upload_id"], "topic": topic}, headers={**H, **KEY})
check("a visitor with their own key is not stopped by the shared daily cap", r.status_code == 201, r.get_data(as_text=True)[:200])
_app.DAILY_AI_LIMIT = 0

print("\n" + ("ALL TESTS PASSED" if not failures else f"{len(failures)} FAILED: {failures}"))
sys.exit(1 if failures else 0)
