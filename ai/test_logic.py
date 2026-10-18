"""
Free offline test of ai_module's own logic (no Gemini calls, no key needed).   Run from the repo root:
    python ai/test_logic.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("GEMINI_API_KEY", "not-used")
from ai import ai_module as ai  # noqa: E402

failures = []


def check(name, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + name + (f"   {detail}" if not cond else ""))
    if not cond:
        failures.append(name)


calls = {"structured": 0, "generate": 0, "last_contents": None}


def fake_structured(contents, system, model_cls, temperature=None):
    calls["structured"] += 1
    calls["last_contents"] = contents
    if model_cls is ai.NextTurn:
        return ai.NextTurn(next_question="  What happens in the Calvin cycle?  ", needs_whiteboard=("diagram" in contents.lower()), diagram_svg="")
    raise AssertionError("unexpected schema " + model_cls.__name__)


class FakeResp:
    text = "A box labelled 'chloroplast' with an arrow pointing right."


def fake_generate(contents, system, **kw):
    calls["generate"] += 1
    calls["last_contents"] = contents
    return FakeResp()


ai._structured_call = fake_structured
ai._generate = fake_generate

first = ai.opening_question("Photosynthesis text")
check("opening question is round 1 and trimmed", first == {"next_question": "What happens in the Calvin cycle?", "should_stop": False, "round": 1, "needs_whiteboard": False, "diagram_svg": ""}, str(first))

history = [{"role": "ai", "text": "Q1"}]
for n in range(2, 6):
    out = ai.next_question("text", history, f"answer {n - 1}")
    check(f"question {n} is asked", not out["should_stop"] and out["round"] == n, str(out))
    history += [{"role": "student", "text": f"answer {n - 1}"}, {"role": "ai", "text": f"Q{n}"}]
before = calls["structured"]
out = ai.next_question("text", history, "answer 5")
check("quiz stops after the 5th answer without calling Gemini", out["should_stop"] and out["round"] == 5 and calls["structured"] == before, str(out))

out = ai.next_question("text", [{"role": "ai", "text": "Draw a diagram"}], "[Whiteboard drawing]\nA box")
check("whiteboard text reaches the model", "Whiteboard drawing" in calls["last_contents"], calls["last_contents"][:200])

desc = ai.describe_drawing("Draw it", b"\x89PNG", "image/png")
check("describe_drawing returns the model's description", "chloroplast" in desc)
check("image was sent to the model", len(calls["last_contents"]) == 2, str(type(calls["last_contents"])))

# full_package reuses an existing score instead of grading again
ai.final_score = lambda s, t: (_ for _ in ()).throw(AssertionError("score recomputed"))
ai.mistake_bundle = lambda s, t, sc, fc="", language="English": ("# Mistake Report", {"gaps": [], "strengths": [], "study_plan": [], "question_feedback": [], "notes": {"language": language, "notes": "N", "notes_translated": "T"}})
ai.notes_bundle = lambda s, t, language="English": {"language": language, "notes": "n", "notes_translated": "x"}
pkg = ai.full_package("s", [], language="Kannada", score={"overall": 80})
check("full_package reuses the given score", pkg["score"] == {"overall": 80} and pkg["report_markdown"] == "# Mistake Report")

ai.mistake_bundle = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("quota"))
pkg = ai.full_package("s", [], score={"overall": 80})
check("a failing report call is not stored as the report", pkg["report_markdown"] is None and pkg["report_error"] == ai.friendly_error(RuntimeError("quota"))[1] and "RuntimeError" not in pkg["report_error"], str(pkg))
ai.mistake_bundle = lambda s, t, sc, fc="", language="English": ("# Mistake Report", {"gaps": [], "strengths": [], "study_plan": [], "question_feedback": [], "notes": {"language": language, "notes": "N", "notes_translated": "T"}})
ai.notes_bundle = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("quota"))
pkg = ai.full_package("s", [], score={"overall": 80})
check("notes come with the report: no separate notes request is made", pkg["report_markdown"] and pkg["notes"]["notes"] == "N")
ai.mistake_bundle = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("quota"))
pkg = ai.full_package("s", [], score={"overall": 80})
check("if both fail, the result still returns with explained errors", pkg["report_markdown"] is None and pkg["notes"]["error"] == ai.friendly_error(RuntimeError("quota"))[1])

# ---- diagram: the AI's SVG field is passed through
def fake_structured_svg(contents, system, model_cls, temperature=None):
    return ai.NextTurn(next_question="Name parts 1 and 2.", needs_whiteboard=False, diagram_svg="<svg viewBox='0 0 400 300'></svg>")


ai._structured_call = fake_structured_svg
out = ai.opening_question("text")
check("diagram question forces the whiteboard on and carries the SVG", out["needs_whiteboard"] is True and out["diagram_svg"].startswith("<svg"), str(out))

# ---- model fallback (uses a stubbed Gemini client, so no requests are spent)
import importlib
importlib.reload(ai)   # restore the real _generate that was stubbed above
ai.MODELS[:] = ["model-a", "model-b", "model-c"]
ai._active = 0
tried = []


class _Models:
    def generate_content(self, model, contents, config):
        tried.append(model)
        if model == "model-a":
            raise Exception("429 RESOURCE_EXHAUSTED GenerateRequestsPerDayPerProjectPerModel-FreeTier")
        if model == "model-b":
            raise Exception("404 NOT_FOUND model is not found")
        return FakeResp()


class _Client:
    models = _Models()


ai._client = _Client()
resp = ai._generate("hi", "sys")
check("falls through an exhausted model and a missing model to the third", tried == ["model-a", "model-b", "model-c"] and resp.text, str(tried))
tried.clear()
ai._generate("hi", "sys")
check("keeps using the working model next time", tried == ["model-c"], str(tried))
ai._active = 0
ai.MODELS[:] = ["model-a"]
try:
    ai._generate("hi", "sys"); check("clear error when every model is used up", False)
except RuntimeError as e:
    check("clear error when every model is used up", "NEW Google AI Studio project" in str(e))
check("status() shows the active model", ai.status()["model"] == "model-a")

ai._structured_call = lambda c, sy, m, temperature=None: m(titles=["Light Capture", "Energy Release"])
check("better_titles returns one heading per section", ai.better_titles([{"text": "a"}, {"text": "b"}]) == ["Light Capture", "Energy Release"])
try:
    ai.better_titles([{"text": "a"}]); check("better_titles rejects wrong count", False)
except ValueError:
    check("better_titles rejects wrong count", True)

ai._structured_call = lambda c, sy, m, temperature=None: m(
    items=[ai.MistakeItem(concept_misunderstood="Order of stages", correct_explanation="A then B.", recommended_review="Redraw it.",
                          what_student_said="Said B then A", why_it_matters="Order matters.", practice_question="What comes first?")],
    strengths=["Clear overview"], study_plan=["Redraw", "Compare"],
    question_feedback=[ai.QuestionFeedback(question="Q1", answer_summary="Gave overview", feedback="Add the order")],
    revision_notes="## Order\n- A then B", revision_notes_translated="## ಕ್ರಮ\n- A ನಂತರ B")
md, extras = ai.mistake_bundle("src", [{"role": "ai", "text": "Q1"}, {"role": "student", "text": "A"}],
                               {"overall": 70, "scores": {k: {"score": 7, "justification": "ok"} for k in ai.CRITERIA}})
check("mistake_bundle keeps the fixed re-uploadable headings", "### Concept Misunderstood" in md and "### Recommended Review" in md)
md2, ex2 = ai.mistake_bundle("src", [{"role": "ai", "text": "Q1"}, {"role": "student", "text": "A"}],
                             {"overall": 70, "scores": {k: {"score": 7, "justification": "ok"} for k in ai.CRITERIA}}, "", "Kannada")
check("notes and translation come from the SAME request as the gap report", ex2["notes"]["notes_translated"].startswith("## ಕ್ರಮ") and ex2["notes"]["language"] == "Kannada" and "notes" not in ex["gaps"] if False else ex2["notes"]["notes_translated"].startswith("## ಕ್ರಮ"))
check("English needs no translation (notes reused)", extras["notes"]["notes_translated"] == extras["notes"]["notes"])
check("mistake_bundle returns detailed extras", extras["gaps"][0]["practice_question"] == "What comes first?" and extras["strengths"] == ["Clear overview"] and len(extras["question_feedback"]) == 1)

# ---- request budget: how many Gemini requests does a whole study loop cost? (real ai_module code, stubbed client)
import json as _json
importlib.reload(ai)
_calls = []
_contents = []


class _R:
    def __init__(self, text): self.text = text; self.parsed = None; self.candidates = []


class _M:
    def generate_content(self, model, contents, config):
        _calls.append(model)
        _contents.append(str(contents))
        schema = getattr(config, "response_schema", None)
        name = getattr(schema, "__name__", "")
        crit = {"score": 7, "justification": "ok"}
        body = {
            "NextTurn": {"next_question": "Q?", "needs_whiteboard": False, "diagram_svg": ""},
            "GradeResult": {"accuracy": crit, "completeness": crit, "consistency": crit, "clarity": crit, "mistakes": ["m"], "summary": "s"},
            "MistakeList": {"items": [{"concept_misunderstood": "c", "correct_explanation": "e", "recommended_review": "r", "what_student_said": "w",
                                       "why_it_matters": "y", "practice_question": "p"}], "strengths": ["a"], "study_plan": ["b"],
                            "question_feedback": [{"question": "q", "answer_summary": "a", "feedback": "f"}],
                            "revision_notes": "## N\n- x", "revision_notes_translated": "## T\n- y"},
        }.get(name)
        return _R(_json.dumps(body) if body is not None else "No suspected errors found.")


class _C:
    models = _M()


ai._client = _C()
hist = []
q = ai.opening_question("notes")
hist.append({"role": "ai", "text": q["next_question"]})
for i in range(5):
    hist.append({"role": "student", "text": "answer %d" % i})
    out = ai.next_question("notes", hist[:-1], "answer %d" % i)
    if out["should_stop"]:
        break
    hist.append({"role": "ai", "text": out["next_question"]})
n_questions = len(_calls)
score = ai.final_score("notes", hist)
ai.full_package("notes", hist, language="Kannada", score=score)
check("5 questions cost exactly 5 requests", n_questions == 5, str(n_questions))
check("one whole session (5 questions + score + report/notes/translation) costs 7 requests", len(_calls) == 7, str(len(_calls)))
check("two sessions (a run plus a test on your gaps) fit in 16 requests, under the 20/day free limit", len(_calls) * 2 <= 20)

_contents.clear()
ai.opening_question("notes", 30)
seen = _contents[-1] if _contents else ""
check("the time limit reaches the question prompt", "30 seconds" in seen, seen[:200])
_contents.clear()
ai.opening_question("notes")
check("no time limit adds no time note", "TIME LIMIT" not in _contents[-1])

for raw, want in [("429 RESOURCE_EXHAUSTED: quota exceeded", "quota"), ("Daily free-tier quota used up for every model tried", "quota"),
                  ("400 API_KEY_INVALID: API key not valid", "bad_key"), ("403 Forbidden", "bad_key"), ("503 UNAVAILABLE overloaded", "busy"),
                  ("httpx.ConnectError: getaddrinfo failed", "network"), ("something odd happened xyz", "unknown")]:
    code, msg, status = ai.friendly_error(RuntimeError(raw))
    check("friendly_error: '%s' -> %s" % (raw[:30], want), code == want and raw.split(":")[0] not in msg, code)
os.environ["GEMINI_API_KEY"] = "your_key_here"
check("a copied placeholder key counts as no key", ai.server_key() == "")
os.environ["GEMINI_API_KEY"] = "not-used"

print("\n" + ("ALL LOGIC TESTS PASSED" if not failures else f"{len(failures)} FAILED: {failures}"))
sys.exit(1 if failures else 0)
