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
ai.fact_check = lambda s, t=None: {"findings": "No suspected errors found.", "sources": []}
ai.mistake_bundle = lambda s, t, sc, fc="": ("# Mistake Report", {"gaps": [], "strengths": [], "study_plan": [], "question_feedback": []})
ai.notes_bundle = lambda s, t, language="English": {"language": language, "notes": "n", "notes_translated": "x"}
pkg = ai.full_package("s", [], language="Kannada", score={"overall": 80})
check("full_package reuses the given score", pkg["score"] == {"overall": 80} and pkg["report_markdown"] == "# Mistake Report")

ai.mistake_bundle = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("quota"))
pkg = ai.full_package("s", [], score={"overall": 80})
check("a failing report call is not stored as the report", pkg["report_markdown"] is None and pkg["report_error"] == "quota", str(pkg))
ai.mistake_bundle = lambda s, t, sc, fc="": ("# Mistake Report", {"gaps": [], "strengths": [], "study_plan": [], "question_feedback": []})
ai.notes_bundle = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("quota"))
pkg = ai.full_package("s", [], score={"overall": 80})
check("a failing notes call does not lose the report", pkg["report_markdown"] and pkg["notes"]["error"] == "quota")

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
    question_feedback=[ai.QuestionFeedback(question="Q1", answer_summary="Gave overview", feedback="Add the order")])
md, extras = ai.mistake_bundle("src", [{"role": "ai", "text": "Q1"}, {"role": "student", "text": "A"}],
                               {"overall": 70, "scores": {k: {"score": 7, "justification": "ok"} for k in ai.CRITERIA}})
check("mistake_bundle keeps the fixed re-uploadable headings", "### Concept Misunderstood" in md and "### Recommended Review" in md)
check("mistake_bundle returns detailed extras", extras["gaps"][0]["practice_question"] == "What comes first?" and extras["strengths"] == ["Clear overview"] and len(extras["question_feedback"]) == 1)

print("\n" + ("ALL LOGIC TESTS PASSED" if not failures else f"{len(failures)} FAILED: {failures}"))
sys.exit(1 if failures else 0)
