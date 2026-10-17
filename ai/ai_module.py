"""
AI module (P1). Pure data in, data out: no input(), no print().
The backend (P3) imports these functions:

    next_question(source_text, conversation_history, new_user_reply) -> dict
    final_score(source_text, transcript)                              -> dict
    fact_check(source_text, transcript=None)                          -> dict
    mistake_report(source_text, transcript, score, fact_check_text="") -> str (Markdown)
    notes_bundle(source_text, transcript, language="Kannada")         -> dict
    full_package(source_text, transcript, language="Kannada")         -> dict

A conversation is a list of messages: {"role": "student" | "ai", "text": "..."}
The first student message is their initial explanation.
"""
import os
import re
import time

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel

try:
    from . import prompts          # when imported as ai.ai_module
except ImportError:
    import prompts                 # when run from inside the ai/ folder

load_dotenv()

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
MAX_ROUNDS = 5
GRADER_TEMPERATURE = float(os.getenv("GRADER_TEMPERATURE", "0.2"))
MAX_RETRIES = 4
RETRY_WAIT_SECONDS = 15

CRITERIA = ["accuracy", "completeness", "consistency", "clarity"]
REPORT_HEADINGS = ["### Concept Misunderstood", "### Correct Explanation", "### Recommended Review"]


# ------------------------------------------------------------------ schemas
class NextTurn(BaseModel):
    next_question: str
    should_stop: bool


class CriterionScore(BaseModel):
    score: int
    justification: str


class GradeResult(BaseModel):
    accuracy: CriterionScore
    completeness: CriterionScore
    consistency: CriterionScore
    clarity: CriterionScore
    mistakes: list[str]
    summary: str


class MistakeItem(BaseModel):
    concept_misunderstood: str
    correct_explanation: str
    recommended_review: str


class MistakeList(BaseModel):
    items: list[MistakeItem]


# ------------------------------------------------------------------ helpers
_client = None


def _get_client():
    global _client
    if _client is None:
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY is missing. Put it in a .env file (see .env.example).")
        _client = genai.Client(api_key=key)
    return _client


def _generate(contents, system, schema=None, temperature=None, tools=None):
    """One Gemini call, retried on rate-limit / overload errors."""
    cfg = {"system_instruction": system}
    if schema is not None:
        cfg["response_mime_type"] = "application/json"
        cfg["response_schema"] = schema
    if temperature is not None:
        cfg["temperature"] = temperature
    if tools:
        cfg["tools"] = tools
    config = types.GenerateContentConfig(**cfg)

    for attempt in range(MAX_RETRIES):
        try:
            return _get_client().models.generate_content(model=MODEL, contents=contents, config=config)
        except Exception as e:  # noqa: BLE001
            if "PerDay" in str(e):   # daily quota: waiting 15 seconds will not help, so fail fast
                raise RuntimeError(
                    f"Daily free-tier quota used up for model '{MODEL}'. Switch GEMINI_MODEL in .env, "
                    "wait for the reset, or enable billing on the project."
                ) from e
            retryable = any(t in str(e) for t in ("429", "503", "RESOURCE_EXHAUSTED", "UNAVAILABLE", "overloaded"))
            if retryable and attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_WAIT_SECONDS * (attempt + 1))
                continue
            raise


def _parse(resp, model_cls):
    parsed = getattr(resp, "parsed", None)
    if isinstance(parsed, model_cls):
        return parsed
    text = (resp.text or "").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text).strip()
    return model_cls.model_validate_json(text)


def _structured_call(contents, system, model_cls, temperature=None):
    """Structured JSON call. If the reply cannot be parsed, retry once."""
    last_error = None
    for _ in range(2):
        resp = _generate(contents, system, schema=model_cls, temperature=temperature)
        try:
            return _parse(resp, model_cls)
        except Exception as e:  # noqa: BLE001
            last_error = e
    raise ValueError(f"Model did not return valid JSON: {last_error}")


def format_transcript(transcript):
    """Accepts a list of {"role","text"} messages or an already-formatted string."""
    if isinstance(transcript, str):
        return transcript
    lines = []
    for m in transcript:
        label = "STUDENT" if m["role"] == "student" else "AI QUESTION"
        lines.append(f"{label}: {m['text']}")
    return "\n".join(lines)


def _clamp(n, low=0, high=10):
    try:
        return max(low, min(high, int(n)))
    except (TypeError, ValueError):
        return low


# ------------------------------------------------------------------ Function 1: loop step
def next_question(source_text, conversation_history, new_user_reply):
    """
    Returns {"next_question": str, "should_stop": bool, "round": int}.
    `conversation_history` is everything BEFORE new_user_reply.
    Stops after MAX_ROUNDS questions, or earlier if the model says the topic is covered.
    """
    history = list(conversation_history or []) + [{"role": "student", "text": new_user_reply}]
    questions_asked = sum(1 for m in history if m["role"] == "ai")

    if questions_asked >= MAX_ROUNDS:
        return {"next_question": "", "should_stop": True, "round": questions_asked}

    contents = (
        f"REFERENCE TEXT:\n{source_text}\n\n"
        f"CONVERSATION SO FAR:\n{format_transcript(history)}\n\n"
        "Write your next turn."
    )
    turn = _structured_call(contents, prompts.QUESTION_SYSTEM, NextTurn)

    question = (turn.next_question or "").strip()
    stop = bool(turn.should_stop) or not question
    return {
        "next_question": "" if stop else question,
        "should_stop": stop,
        "round": questions_asked if stop else questions_asked + 1,
    }


# ------------------------------------------------------------------ Function 2: grader
def final_score(source_text, transcript):
    """
    Returns:
    {
      "scores": {"accuracy": {"score": 0-10, "justification": str}, ... 4 criteria},
      "overall": 0-100,           # computed in code, not by the model
      "mistakes": [str, ...],
      "summary": str
    }
    """
    contents = (
        f"REFERENCE TEXT:\n{source_text}\n\n"
        f"TRANSCRIPT:\n{format_transcript(transcript)}\n\n"
        "Grade the student now."
    )
    grade = _structured_call(contents, prompts.GRADER_SYSTEM, GradeResult, temperature=GRADER_TEMPERATURE)

    scores = {}
    for name in CRITERIA:
        item = getattr(grade, name)
        scores[name] = {"score": _clamp(item.score), "justification": item.justification.strip()}
    overall = round(sum(s["score"] for s in scores.values()) / len(CRITERIA) * 10)
    return {
        "scores": scores,
        "overall": overall,
        "mistakes": [m.strip() for m in grade.mistakes if m.strip()],
        "summary": grade.summary.strip(),
    }


# ------------------------------------------------------------------ Milestone 6: fact-check
def fact_check(source_text, transcript=None):
    """
    Google Search grounded check. Returns {"findings": str, "sources": [{"title","url"}]}.
    Output is plain text because structured JSON and search grounding are not reliably combinable.
    """
    contents = f"REFERENCE TEXT:\n{source_text}\n"
    if transcript:
        contents += f"\nTRANSCRIPT:\n{format_transcript(transcript)}\n"
    tools = [types.Tool(google_search=types.GoogleSearch())]
    resp = _generate(contents, prompts.FACT_CHECK_SYSTEM, tools=tools)

    sources, seen = [], set()
    try:
        meta = resp.candidates[0].grounding_metadata
        for chunk in (getattr(meta, "grounding_chunks", None) or []):
            web = getattr(chunk, "web", None)
            url = getattr(web, "uri", None)
            if url and url not in seen:
                seen.add(url)
                sources.append({"title": getattr(web, "title", "") or url, "url": url})
    except (AttributeError, IndexError, TypeError):
        pass
    return {"findings": (resp.text or "").strip(), "sources": sources}


# ------------------------------------------------------------------ Milestone 6: mistake report
def mistake_report(source_text, transcript, score, fact_check_text=""):
    """
    Markdown report with FIXED headings (see REPORT_HEADINGS) so it can be re-uploaded and parsed.
    Each mistake block is separated by a line containing only '---'.
    """
    contents = (
        f"REFERENCE TEXT:\n{source_text}\n\n"
        f"TRANSCRIPT:\n{format_transcript(transcript)}\n\n"
        f"SCORES: {score['scores']}\n"
    )
    items = _structured_call(contents, prompts.MISTAKES_SYSTEM, MistakeList).items

    lines = ["# Mistake Report", "", "## Score Summary", f"- Overall: {score['overall']}/100"]
    for name in CRITERIA:
        lines.append(f"- {name.capitalize()}: {score['scores'][name]['score']}/10")
    lines += ["", "## Mistakes", ""]
    if not items:
        lines.append("No significant mistakes found.")
    for i, it in enumerate(items):
        if i:
            lines += ["---", ""]
        lines += [
            REPORT_HEADINGS[0], it.concept_misunderstood.strip(), "",
            REPORT_HEADINGS[1], it.correct_explanation.strip(), "",
            REPORT_HEADINGS[2], it.recommended_review.strip(), "",
        ]
    if fact_check_text:
        lines += ["## Suspected Issues In Study Material", fact_check_text.strip(), ""]
    return "\n".join(lines).strip() + "\n"


# ------------------------------------------------------------------ Milestone 7: notes + translation
def notes_bundle(source_text, transcript, language="Kannada"):
    """Returns {"language", "notes", "notes_translated"}."""
    contents = f"REFERENCE TEXT:\n{source_text}\n\nTRANSCRIPT:\n{format_transcript(transcript)}\n"
    notes = (_generate(contents, prompts.NOTES_SYSTEM).text or "").strip()
    translated = (_generate(notes, prompts.TRANSLATE_SYSTEM.format(language=language)).text or "").strip()
    return {"language": language, "notes": notes, "notes_translated": translated}


# ------------------------------------------------------------------ one call for P3 at session end
def full_package(source_text, transcript, language="Kannada"):
    """
    Everything the results and report pages need. The score is required; the optional
    parts never crash the result, they return an "error" string instead.
    """
    score = final_score(source_text, transcript)
    package = {"score": score, "fact_check": None, "report_markdown": None, "notes": None}

    try:
        package["fact_check"] = fact_check(source_text, transcript)
    except Exception as e:  # noqa: BLE001
        package["fact_check"] = {"findings": "", "sources": [], "error": str(e)}

    try:
        fc_text = package["fact_check"]["findings"]
        if fc_text.startswith("No suspected errors"):
            fc_text = ""
        package["report_markdown"] = mistake_report(source_text, transcript, score, fc_text)
    except Exception as e:  # noqa: BLE001
        package["report_markdown"] = f"Report unavailable: {e}"

    try:
        package["notes"] = notes_bundle(source_text, transcript, language)
    except Exception as e:  # noqa: BLE001
        package["notes"] = {"language": language, "notes": "", "notes_translated": "", "error": str(e)}
    return package
