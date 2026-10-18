"""
AI module (P1). Pure data in, data out: no input(), no print().
The backend (P3) imports these functions:

    opening_question(source_text)                                     -> dict   (the AI starts the quiz)
    next_question(source_text, conversation_history, new_user_reply) -> dict
    describe_drawing(question, image_bytes, mime_type)                -> str    (reads a whiteboard drawing)
    final_score(source_text, transcript)                              -> dict
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
    revision_notes: str              # Markdown study notes in English (see the prompt)
    revision_notes_translated: str   # the same notes in the requested language ("" or identical when English)


# ------------------------------------------------------------------ helpers
_client = None         # a forced client (tests replace it with a stub); normally clients are created per key below
_requests = 0          # successful Gemini requests since the server started (shown in the app so you can plan your quota)

# ---- a visitor can bring their own key: it is held for the duration of one request only (never written to disk or logs)
import contextvars   # noqa: E402
import hashlib       # noqa: E402

_user_key = contextvars.ContextVar("vocalis_user_key", default="")
_clients = {}          # key -> genai.Client (kept in memory so each request does not rebuild it)
_counts = {}           # key fingerprint -> successful requests made with that key
_active_by = {}        # key fingerprint -> index of the model in use for that key


def use_key(key):
    """Use this Gemini key for the current request ("" = the server's own key)."""
    _user_key.set((key or "").strip())


_PLACEHOLDERS = ("your_key", "your-key", "paste", "changeme", "xxxx", "insert", "<", "none", "null")


def server_key():
    """The key set by the site owner in .env or the host, or "" when there is none (a copied placeholder such as your_key_here counts as none)."""
    if os.getenv("REQUIRE_USER_KEY", "0") == "1":
        return ""          # ignore any key on the machine (even one left in Windows environment variables): visitors must bring their own
    key = (os.getenv("GEMINI_API_KEY") or "").strip().strip('"').strip("'")
    low = key.lower()
    if not key or any(low.startswith(x) or x in low for x in _PLACEHOLDERS if x != "<") or "<" in key:
        return ""
    return key


def _current_key():
    return _user_key.get() or server_key()


def friendly_error(e):
    """Turns any Gemini failure into (code, plain message, http status). The raw text is never shown to the user."""
    t = str(e)
    low = t.lower()
    if "api_key_invalid" in low or "api key not valid" in low or "permission_denied" in low or "unauthenticated" in low \
            or "403" in t or "401" in t or "no gemini api key" in low or "api key" in low and "invalid" in low:
        return ("bad_key", "Gemini did not accept this API key. Check that you copied all of it, or create a new one at aistudio.google.com/apikey.", 403)
    if "resource_exhausted" in low or "429" in t or "quota" in low or "perday" in low or "used up" in low or "rate limit" in low:
        return ("quota", "This API key has used up its free Gemini requests for today. They reset every day. You can come back later, or add a different key.", 429)
    if "503" in t or "unavailable" in low or "overloaded" in low or " 500" in t or "deadline" in low or "internal error" in low:
        return ("busy", "Gemini is busy right now. Wait a minute and try again.", 503)
    if any(x in low for x in ("connect", "timed out", "timeout", "getaddrinfo", "name resolution", "network", "ssl")):
        return ("network", "Could not reach Gemini. Check your internet connection and try again.", 502)
    if any(x in low for x in ("safety", "blocked", "prohibited", "recitation")):
        return ("blocked", "Gemini would not answer that. Try different wording or another part of your notes.", 422)
    return ("unknown", "The AI had a problem with that request. Please try again.", 502)


def _fp(key):
    return hashlib.sha256(key.encode()).hexdigest()[:12] if key else ""


def usage(key):
    """Requests made with this key since the server started."""
    return _counts.get(_fp(key), 0)


def _get_client():
    if _client is not None:
        return _client
    key = _current_key()
    if not key:
        raise RuntimeError("No Gemini API key. Click the key button at the top of the page and paste yours (free at aistudio.google.com/apikey).")
    c = _clients.get(key)
    if c is None:
        if len(_clients) > 200:
            _clients.clear()
        c = _clients[key] = genai.Client(api_key=key)
    return c


def check_key():
    """One tiny request to prove the current key works. Returns the model that answered."""
    resp = _generate("Reply with the single word OK.", "You answer with one word.")
    return {"ok": True, "model": MODELS[0], "reply": (resp.text or "").strip()[:20]}


def status():
    """What the app is really using (shown by /health and at startup). Only the last 4 characters of the key are shown."""
    key = server_key()
    return {"model": MODELS[min(_active, len(MODELS) - 1)], "models": MODELS, "key_ending": key[-4:] if key else None, "requests": _requests}


class _ModelOut(Exception):
    """This model cannot be used right now (daily quota used up, or unknown name)."""


def _call_model(model, contents, config):
    for attempt in range(MAX_RETRIES):
        try:
            out = _get_client().models.generate_content(model=model, contents=contents, config=config)
            global _requests
            _requests += 1
            f = _fp(_user_key.get())
            if f:
                _counts[f] = _counts.get(f, 0) + 1
            return out
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
    global _active
    fp = _fp(_user_key.get())
    start = _active_by.get(fp, 0) if fp else _active
    for idx in range(start, len(MODELS)):
        try:
            resp = _call_model(MODELS[idx], contents, config)
            if idx != start:
                print(f"[ai] switched to model '{MODELS[idx]}' ({'; '.join(reasons)})")
                if fp:
                    _active_by[fp] = idx
                else:
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
def _time_note(time_limit):
    if not time_limit:
        return ""
    return f"TIME LIMIT: the explainer has {int(time_limit)} seconds to answer each question, so ask something that can be answered well within that.\n\n"


def _ask(source_text, history, time_limit=0):
    contents = (
        _time_note(time_limit) +
        f"REFERENCE TEXT:\n{source_text}\n\n"
        f"CONVERSATION SO FAR:\n{format_transcript(history) if history else '(empty: this is question 1)'}\n\n"
        "Write your next question."
    )
    return _structured_call(contents, prompts.QUESTION_SYSTEM, NextTurn)


def opening_question(source_text, time_limit=0):
    """The AI starts the conversation. Returns {"next_question", "should_stop": False, "round": 1, "needs_whiteboard", "diagram_svg"}."""
    turn = _ask(source_text, [], time_limit)
    question = (turn.next_question or "").strip() or "In your own words, what is the main idea of this topic?"
    return {"next_question": question, "should_stop": False, "round": 1, "needs_whiteboard": bool(turn.needs_whiteboard) or bool(turn.diagram_svg),
            "diagram_svg": turn.diagram_svg or ""}


def next_question(source_text, conversation_history, new_user_reply, time_limit=0):
    """
    Returns {"next_question": str, "should_stop": bool, "round": int, "needs_whiteboard": bool}.
    `conversation_history` is everything BEFORE new_user_reply and starts with the AI's first question.
    The quiz is exactly MAX_ROUNDS questions: it stops once the last question has been answered.
    """
    history = list(conversation_history or []) + [{"role": "student", "text": new_user_reply}]
    questions_asked = sum(1 for m in history if m["role"] == "ai")
    if questions_asked >= MAX_ROUNDS:
        return {"next_question": "", "should_stop": True, "round": questions_asked, "needs_whiteboard": False, "diagram_svg": ""}

    turn = _ask(source_text, history, time_limit)
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


# ------------------------------------------------------------------ Milestone 6: mistake report
def mistake_bundle(source_text, transcript, score, fact_check_text="", language="English"):
    """
    Returns (markdown, extras). The Markdown has FIXED headings (see REPORT_HEADINGS) so it can be re-uploaded and parsed;
    each mistake block is separated by a line containing only '---'. extras holds the detailed material used by the Word reports.
    """
    contents = (
        f"REFERENCE TEXT:\n{source_text}\n\n"
        f"TRANSCRIPT:\n{format_transcript(transcript)}\n\n"
        f"SCORES: {score['scores']}\n"
    )
    system = prompts.MISTAKES_SYSTEM.replace("{language}", language or "English")
    data = _structured_call(contents, system, MistakeList)
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
        "notes": {
            "language": language,
            "notes": data.revision_notes.strip(),
            "notes_translated": (data.revision_notes.strip() if (language or "English").strip().lower() == "english"
                                 else data.revision_notes_translated.strip()),
        },
    }
    return "\n".join(lines).strip() + "\n", extras


def mistake_report(source_text, transcript, score, fact_check_text="", language="English"):
    """Markdown gap report only (see mistake_bundle)."""
    return mistake_bundle(source_text, transcript, score, fact_check_text, language)[0]


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
def full_package(source_text, transcript, language="English", include_notes=True, score=None):
    """
    Everything the report page needs, in order of importance so the essential parts exist even if the quota runs out half way:
      1. score (skipped when given)   2. gap report + strengths + study plan + question feedback + notes + translation (ONE request)
    """
    score = score or final_score(source_text, transcript)
    package = {"score": score, "report_markdown": None, "notes": None}

    try:
        package["report_markdown"], extras = mistake_bundle(source_text, transcript, score, "", language)
        notes = extras.pop("notes", None)
        package.update(extras)
        if include_notes:
            package["notes"] = notes
    except Exception as e:  # noqa: BLE001
        package["report_markdown"] = None            # never store an error message as if it were the report
        package["report_error"] = friendly_error(e)[1]
        if include_notes:                            # the older, separate notes request as a fallback
            try:
                package["notes"] = notes_bundle(source_text, transcript, language)
            except Exception as e2:  # noqa: BLE001
                package["notes"] = {"language": language, "notes": "", "notes_translated": "", "error": friendly_error(e2)[1]}

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
