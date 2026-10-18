"""
AI module (P1). Pure data in, data out: no input(), no print().
The backend (P3) imports these functions:

    opening_question(source_text)                                     -> dict   (the AI starts the quiz)
    next_question(source_text, conversation_history, new_user_reply) -> dict
    describe_drawing(question, image_bytes, mime_type)                -> str    (reads a whiteboard drawing)
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

from dotenv import dotenv_values, load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel

try:
    from . import prompts          # when imported as ai.ai_module
except ImportError:
    import prompts                 # when run from inside the ai/ folder

load_dotenv()
# The GEMINI_* settings in .env win over an old GEMINI_API_KEY left in the Windows environment variables.
for _k, _v in dotenv_values(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")).items():
    if _k.startswith("GEMINI_") and _v:
        os.environ[_k] = _v

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
# When a model's free daily quota is used up (or the name does not exist), the next one in this list is tried automatically.
FALLBACK_MODELS = [m.strip() for m in os.getenv("GEMINI_FALLBACK_MODELS", "gemini-2.5-flash,gemini-2.5-flash-lite").split(",") if m.strip()]
MODELS = [MODEL] + [m for m in FALLBACK_MODELS if m != MODEL]
_active = 0   # index into MODELS of the model currently in use; moves forward when a model runs out
MAX_ROUNDS = 5
GRADER_TEMPERATURE = float(os.getenv("GRADER_TEMPERATURE", "0.2"))
MAX_RETRIES = 4
RETRY_WAIT_SECONDS = 15

CRITERIA = ["accuracy", "completeness", "consistency", "clarity"]
REPORT_HEADINGS = ["### Concept Misunderstood", "### Correct Explanation", "### Recommended Review"]


# ------------------------------------------------------------------ schemas
class NextTurn(BaseModel):
    next_question: str
    needs_whiteboard: bool
    diagram_svg: str           # empty string when no diagram is needed


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
    what_student_said: str      # the student's own words (short quote or paraphrase), or "Not mentioned"
    why_it_matters: str
    practice_question: str


class QuestionFeedback(BaseModel):
    question: str
    answer_summary: str
    feedback: str


class MistakeList(BaseModel):
    items: list[MistakeItem]
    strengths: list[str]
    study_plan: list[str]
    question_feedback: list[QuestionFeedback]


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


def status():
    """What the app is really using (shown by /health and at startup). Only the last 4 characters of the key are shown."""
    key = os.getenv("GEMINI_API_KEY") or ""
    return {"model": MODELS[min(_active, len(MODELS) - 1)], "models": MODELS, "key_ending": key[-4:] if key else None}


class _ModelOut(Exception):
    """This model cannot be used right now (daily quota used up, or unknown name)."""


def _call_model(model, contents, config):
    for attempt in range(MAX_RETRIES):
        try:
            return _get_client().models.generate_content(model=model, contents=contents, config=config)
        except Exception as e:  # noqa: BLE001
            text = str(e)
            if "PerDay" in text:   # daily quota: waiting 15 seconds will not help
                raise _ModelOut(f"daily quota used up for '{model}'") from e
            if "NOT_FOUND" in text or "is not found" in text:
                raise _ModelOut(f"model '{model}' not found") from e
            retryable = any(t in text for t in ("429", "503", "RESOURCE_EXHAUSTED", "UNAVAILABLE", "overloaded"))
            if retryable and attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_WAIT_SECONDS * (attempt + 1))
                continue
            raise


def _generate(contents, system, schema=None, temperature=None, tools=None):
    """One Gemini call, retried on rate-limit / overload errors, falling back to the next model when one is used up."""
    global _active
    cfg = {"system_instruction": system}
    if schema is not None:
        cfg["response_mime_type"] = "application/json"
        cfg["response_schema"] = schema
    if temperature is not None:
        cfg["temperature"] = temperature
    if tools:
        cfg["tools"] = tools
    config = types.GenerateContentConfig(**cfg)

    reasons = []
    for idx in range(_active, len(MODELS)):
        try:
            resp = _call_model(MODELS[idx], contents, config)
            if idx != _active:
                print(f"[ai] switched to model '{MODELS[idx]}' ({'; '.join(reasons)})")
                _active = idx
            return resp
        except _ModelOut as e:
            reasons.append(str(e))
    raise RuntimeError(
        "Daily free-tier quota used up for every model tried (" + "; ".join(reasons) + "). "
        "Use an API key from a NEW Google AI Studio project, add other models to GEMINI_FALLBACK_MODELS in .env, "
        "wait for the reset, or enable billing."
    )


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


# ------------------------------------------------------------------ Function 1: the question loop
def _ask(source_text, history):
    contents = (
        f"REFERENCE TEXT:\n{source_text}\n\n"
        f"CONVERSATION SO FAR:\n{format_transcript(history) if history else '(empty: this is question 1)'}\n\n"
        "Write your next question."
    )
    return _structured_call(contents, prompts.QUESTION_SYSTEM, NextTurn)


def opening_question(source_text):
    """The AI starts the conversation. Returns {"next_question", "should_stop": False, "round": 1, "needs_whiteboard", "diagram_svg"}."""
    turn = _ask(source_text, [])
    question = (turn.next_question or "").strip() or "In your own words, what is the main idea of this topic?"
    return {"next_question": question, "should_stop": False, "round": 1, "needs_whiteboard": bool(turn.needs_whiteboard) or bool(turn.diagram_svg),
            "diagram_svg": turn.diagram_svg or ""}


def next_question(source_text, conversation_history, new_user_reply):
    """
    Returns {"next_question": str, "should_stop": bool, "round": int, "needs_whiteboard": bool}.
    `conversation_history` is everything BEFORE new_user_reply and starts with the AI's first question.
    The quiz is exactly MAX_ROUNDS questions: it stops once the last question has been answered.
    """
    history = list(conversation_history or []) + [{"role": "student", "text": new_user_reply}]
    questions_asked = sum(1 for m in history if m["role"] == "ai")
    if questions_asked >= MAX_ROUNDS:
        return {"next_question": "", "should_stop": True, "round": questions_asked, "needs_whiteboard": False, "diagram_svg": ""}

    turn = _ask(source_text, history)
    question = (turn.next_question or "").strip()
    if not question:
        return {"next_question": "", "should_stop": True, "round": questions_asked, "needs_whiteboard": False, "diagram_svg": ""}
    return {"next_question": question, "should_stop": False, "round": questions_asked + 1,
            "needs_whiteboard": bool(turn.needs_whiteboard) or bool(turn.diagram_svg), "diagram_svg": turn.diagram_svg or ""}


def describe_drawing(question, image_bytes, mime_type="image/png"):
    """Gemini vision reads the student's whiteboard. Returns a plain-text description (used as part of their answer)."""
    contents = [types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                f"QUESTION THE STUDENT WAS ASKED:\n{question}\n\nDescribe the whiteboard."]
    text = (_generate(contents, prompts.DRAWING_SYSTEM).text or "").strip()
    return text or "The whiteboard is empty."


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
def mistake_bundle(source_text, transcript, score, fact_check_text=""):
    """
    Returns (markdown, extras). The Markdown has FIXED headings (see REPORT_HEADINGS) so it can be re-uploaded and parsed;
    each mistake block is separated by a line containing only '---'. extras holds the detailed material used by the Word reports.
    """
    contents = (
        f"REFERENCE TEXT:\n{source_text}\n\n"
        f"TRANSCRIPT:\n{format_transcript(transcript)}\n\n"
        f"SCORES: {score['scores']}\n"
    )
    data = _structured_call(contents, prompts.MISTAKES_SYSTEM, MistakeList)
    items = data.items

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
    extras = {
        "gaps": [it.model_dump() for it in items],
        "strengths": [x.strip() for x in data.strengths if x.strip()],
        "study_plan": [x.strip() for x in data.study_plan if x.strip()],
        "question_feedback": [q.model_dump() for q in data.question_feedback],
    }
    return "\n".join(lines).strip() + "\n", extras


def mistake_report(source_text, transcript, score, fact_check_text=""):
    """Markdown gap report only (see mistake_bundle)."""
    return mistake_bundle(source_text, transcript, score, fact_check_text)[0]


# ------------------------------------------------------------------ Milestone 7: notes + translation
def notes_bundle(source_text, transcript, language="Kannada"):
    """Returns {"language", "notes", "notes_translated"}."""
    contents = f"REFERENCE TEXT:\n{source_text}\n\nTRANSCRIPT:\n{format_transcript(transcript)}\n"
    notes = (_generate(contents, prompts.NOTES_SYSTEM).text or "").strip()
    if language.strip().lower() == "english":      # nothing to translate: saves one request
        translated = notes
    else:
        translated = (_generate(notes, prompts.TRANSLATE_SYSTEM.format(language=language)).text or "").strip()
    return {"language": language, "notes": notes, "notes_translated": translated}


# ------------------------------------------------------------------ one call at the end of a session
def full_package(source_text, transcript, language="English", include_fact_check=True, include_notes=True, score=None):
    """
    Everything the report page needs. The score and the gap report are required; the fact-check and the notes
    are optional (they cost extra requests) and never crash the result: they return an "error" string instead.
    """
    score = score or final_score(source_text, transcript)
    package = {"score": score, "fact_check": None, "report_markdown": None, "notes": None}

    fc_text = ""
    if include_fact_check:
        try:
            package["fact_check"] = fact_check(source_text, transcript)
            fc_text = package["fact_check"]["findings"]
            if fc_text.startswith("No suspected errors"):
                fc_text = ""
        except Exception as e:  # noqa: BLE001
            package["fact_check"] = {"findings": "", "sources": [], "error": str(e)}

    try:
        package["report_markdown"], extras = mistake_bundle(source_text, transcript, score, fc_text)
        package.update(extras)
    except Exception as e:  # noqa: BLE001
        package["report_markdown"] = None            # never store an error message as if it were the report
        package["report_error"] = str(e)

    if include_notes:
        try:
            package["notes"] = notes_bundle(source_text, transcript, language)
        except Exception as e:  # noqa: BLE001
            package["notes"] = {"language": language, "notes": "", "notes_translated": "", "error": str(e)}
    return package


# ------------------------------------------------------------------ read-aloud voice (Gemini text-to-speech)
TTS_MODEL = os.getenv("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts")
TTS_VOICES = ["Aoede", "Kore", "Leda", "Zephyr", "Puck", "Charon"]


def speak_wav(text, voice="Aoede"):
    """Text -> WAV bytes in a natural AI voice. Costs one request on the TTS model (its own free quota)."""
    import io
    import wave
    voice = voice if voice in TTS_VOICES else TTS_VOICES[0]
    text = (text or "").strip()[:1500]
    if not text:
        raise ValueError("Nothing to read aloud.")
    cfg = types.GenerateContentConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice))),
    )
    last = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = _get_client().models.generate_content(
                model=TTS_MODEL, contents="Say this in a warm, clear, friendly tone: " + text, config=cfg)
            pcm = resp.candidates[0].content.parts[0].inline_data.data
            buf = io.BytesIO()
            with wave.open(buf, "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(pcm)
            return buf.getvalue()
        except Exception as e:  # noqa: BLE001
            last = e
            t = str(e)
            if "PerDay" in t or "NOT_FOUND" in t:
                break
            if any(x in t for x in ("429", "503", "UNAVAILABLE")) and attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_WAIT_SECONDS * (attempt + 1))
                continue
            break
    raise RuntimeError(f"The AI voice is not available right now ({type(last).__name__}). The browser voice is used instead.")


# ------------------------------------------------------------------ better headings for auto-split material
class _Titles(BaseModel):
    titles: list[str]


TITLES_SYSTEM = (
    "You name the sections of a student's study material. For each numbered section you get its first lines. "
    "Return exactly one short, clear heading per section, in the same order: 2 to 7 words, Title Case, "
    "naming the specific idea (e.g. 'How Photosynthesis Captures Light'), never 'Part 1', 'Section', 'Introduction to' or 'Overview of' alone. "
    "No numbering and no quotes."
)


def better_titles(sections):
    """Returns a list of improved headings (same length as sections), or raises."""
    parts = [f"[{i + 1}]\n{(s['text'] or '')[:450]}" for i, s in enumerate(sections)]
    out = _structured_call("\n\n".join(parts), TITLES_SYSTEM, _Titles, temperature=0.3)
    titles = [" ".join(str(t).split()).strip(" .:-\"'")[:80] for t in out.titles]
    if len(titles) != len(sections) or not all(titles):
        raise ValueError("Model returned the wrong number of headings.")
    return titles
