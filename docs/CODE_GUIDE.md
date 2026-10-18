# Vocalis code guide

Every file, what it does, and a few real lines to find it by. Line numbers drift as code changes, so search for the quoted text.

## How one session flows (read this first)

```
upload file ──> ingestion/extract.py ──> sections (topics) ──> database
choose topic + confidence + time limit ──> POST /session/start ──> ai.opening_question
answer (text / voice / drawing) ──> POST /session/answer ──> ai.next_question  (x5)
last answer ──> GET /session/<id>/result ──> ai.final_score, mistake_bundle
report page: gaps, notes, progress graph, badge, integrity verdict, feedback
```

Gemini request cost per session: 5 questions + 1 score + 1 report bundle = **7**. Drawings, accurate voice and the AI read-aloud voice cost +1 each. Everything else (integrity checks, badges, progress graph, stats, Word export) costs 0.

---

## ai/ , everything that talks to Gemini

### ai/ai_module.py
The only file that calls Gemini. Every function returns plain dicts so the backend never sees Gemini objects.

| Part | What it does | Find it by |
|---|---|---|
| Pydantic schemas | Tell Gemini the exact JSON shape to return (`NextTurn`, `GradeResult`, `MistakeItem`, `MistakeList`). All fields are required, no defaults, which Gemini handles reliably. | `class NextTurn(BaseModel):` |
| `_call_model` / `_generate` | One request, retried on rate limits, then falls back to the next model in `MODELS`. Counts successful calls in `_requests`. | `for idx in range(_active, len(MODELS)):` |
| `_structured_call` | `_generate` plus parsing into a schema. | `def _structured_call(` |
| `_time_note`, `_ask` | Adds the chosen time limit to the prompt so questions fit it. | `"TIME LIMIT: the explainer has {int(time_limit)} seconds ..."` |
| `opening_question`, `next_question` | Question 1, then questions 2 to 5. Stops after `MAX_ROUNDS` with no extra call. | `if questions_asked >= MAX_ROUNDS:` |
| `describe_drawing` | Gemini vision reads a whiteboard PNG and describes it objectively; the description is stored as part of the answer. | `def describe_drawing(` |
| `final_score` | Grades 4 criteria 0 to 10. **The overall score is computed in code, not by the model**, so it is consistent. | `overall = round(sum(s["score"] for s in scores.values()) / len(CRITERIA) * 10)` |
| `mistake_bundle` | **One request** returns the gap list, strengths, study plan, per-question feedback, revision notes and their translation. Markdown keeps fixed headings so the report can be re-uploaded. | `### Concept Misunderstood` |
| `full_package` | Orders the work by importance: score, then bundle. If the quota dies half way, the essential parts already exist. | `def full_package(` |
| `speak_wav` | Gemini text-to-speech for the optional AI voice. | `def speak_wav(` |
| `better_titles` | One request that renames generic topic headings. | `def better_titles(` |

### ai/prompts.py
The instructions given to Gemini. Plain text constants.
- `QUESTION_SYSTEM`: the curious-student persona. Key rules: *"Ask exactly one question"*, *"TIME LIMIT: ..."*, *"MATHS AND NUMBERS: ... at least 2 of the 5 questions must be numerical or graphical"*, and the diagram rules with a worked SVG example.
- `GRADER_SYSTEM`: *"You are a strict, consistent examiner"*, with score anchors (0, 5, 10) for accuracy, completeness, consistency and clarity. Anchors are why two runs give similar scores.
- `MISTAKES_SYSTEM`: how to write gaps, strengths, study plan, notes and the translation (`{language}` is filled in by code).
- `NOTES_SYSTEM`, `TRANSLATE_SYSTEM`, `DRAWING_SYSTEM`: notes, translation and whiteboard-reading prompts. (The heading prompt `TITLES_SYSTEM` lives in `ai_module.py`.)

### ai/test_logic.py and ai/test_ai.py
`test_logic.py` stubs the Gemini client and checks everything without a key or quota, including the request budget (*"5 questions cost exactly 5 requests"*, *"one whole session ... costs 7 requests"*) and that the time limit reaches the prompt. `test_ai.py` is a live test that needs a real key.

---

## backend/ , the Flask server

### backend/app.py
Routes (each is `@app.get/post(...)` then a function):

| Route | Purpose |
|---|---|
| `/auth/register`, `/auth/login`, `/auth/me`, `/auth/logout` | Accounts. Tokens never expire. `@login_required` guards the rest. |
| `/upload` | Saves the file, runs ingestion, renames generic headings (`better_headings`). |
| `/session/start` | Reads `time_limit` and `confidence`, asks `ai.opening_question`, creates the session. |
| `/session/answer` | Takes text, audio and/or drawing. Transcribes audio, describes the drawing, runs the integrity check, asks the next question. Saves everything. |
| `/session/<id>/result` | `mode=score` (1 request) or `full`. **Only the missing parts are generated**; saved results are returned with no request: *"everything asked for is already saved: no AI request"*. |
| `/session/<id>/progress` | Scores of every attempt at the same file and topic, for the improvement graph. |
| `/session/<id>/feedback`, `/stats`, `/profile` | Feedback form, anonymous totals for the evidence slide, badge collection. |
| `/session/<id>/export?kind=gaps|notes` | Gap report and revision notes as separate Word files via `export_docx.py` (`full` also exists in the API). |
| `/feedback/summary`, `/feedback/export.csv` | Compiled feedback: anonymous totals, and a CSV of every response (gated by `FEEDBACK_KEY` on a public site). |
| `/tts` | AI voice audio. |
| `/health` | Model name and request counter. |

Also here:
- `over_budget(cost)`: per-user daily cap (`DAILY_AI_LIMIT`) with a friendly 429, which protects the free quota on a public site.
- `with_integrity(package, session)`: adds the honesty verdict, badge, confidence and feedback to a result without changing what is stored.
- The `USE_FAKE_AI` switch near the top swaps in `fake_ai.py` for tests only.

### backend/database.py
SQLite in one file. Tables: `users`, `tokens`, `uploads`, `sessions`, `messages`. `MIGRATIONS` adds new columns to an old database automatically (`time_limit`, `integrity_json`, `confidence`, `feedback_json`). Notable functions: `list_sessions` (history with badges), `attempts_for` (progress graph), `stats` (anonymous evidence numbers).

### backend/integrity.py
Honesty checks, no AI.
- `copy_overlap(answer, material)`: share of the answer's 6-word runs found in the notes, in order. Answers under 12 words are skipped.
- `add_answer`, `verdict`: counts blocked pastes and tab switches, flags the session (*`PASTE_LIMIT = 1`, `TAB_LIMIT = 3`, `OVERLAP_LIMIT = 0.5`*).
- `badge(overall, flagged)`: Platinum 90, Gold 80, Silver 60, Bronze 40; a flagged session gets none.
- `profile(rows)`: tier counts plus the special badges (Improver, Honest scholar ...).

### backend/export_docx.py
Builds the Word files with python-docx. `build_gap_report` (gaps with a tick line, study plan) and `build_full_report` (adds score table, conversation with whiteboard drawings, notes plus translation, page numbers). `autofit = False` keeps table widths.

### backend/svg_clean.py
Security: AI-drawn diagrams are untrusted. `safe_svg` keeps only whitelisted tags and attributes (`TAGS`, `ATTRS`), rejects `url(`/scripts (`BAD_VALUE`), and caps size (`MAX_CHARS`, `MAX_ELEMENTS`). Without it a diagram could carry a script into the page.

### backend/material.py, backend/transcribe.py
Two-line adapters so `app.py` calls the ingestion package through stable names.

### backend/fake_ai.py
Canned AI with the same function names, used only by tests (`USE_FAKE_AI=1`) so the whole flow can be tested with no quota. Not shown to users.

### backend tests
`test_api.py` (every route, login, caps, export, feedback, stats), `test_full_loop.py` (real backend plus real `ai_module` with a stubbed client: 7 requests per session, 14 for session plus retest), `test_integrity.py` (copy overlap, flags, badges).

---

## ingestion/ , turning any file into topics

| File | Role |
|---|---|
| `extract.py` | `extract(path)` picks a reader by extension and returns `[{"title", "text"}, ...]`. Raises `ExtractionError` with a readable message. |
| `pdf_reader.py` | PyMuPDF text; `_drop_repeats` removes headers and footers; `_sections_by_font` finds headings by font size; scanned PDFs go to OCR. |
| `docx_reader.py`, `pptx_reader.py` | Headings and slide titles become topics. `docx_reader` recognises a "Vocalis Gap Report" and turns each gap into a "Mistake N" topic. |
| `image_reader.py` | Photos and scans through Gemini vision OCR (`ocr_pdf` for scanned PDFs). |
| `audio.py` | Audio answers: converts to 16 kHz WAV and transcribes with Gemini. |
| `report_parser.py` | Parses the fixed gap-report headings from a re-uploaded `.md`. |
| `topics.py` | Splitting logic: `split_sections`, `chunk_by_size` (about 3500 characters), `merge_small`, and `retitle_generic` / `guess_title` for weak headings. |
| `_llm.py` | Small shared helper for ingestion's Gemini calls. |
| `errors.py` | `class ExtractionError(Exception)`. |
| `test_ingestion.py` | Tests on the files in `test-material/`. |

---

## frontend/ , the web app (no framework)

### frontend/index.html
One page, several `<section class="screen" id="screen-...">`: auth, home, about, topics, chat, report. JavaScript shows one at a time. Notable ids: `topicSelect` (dropdown), `confSlider` (confidence before), `calcPanel`, `wbCol` (whiteboard), `integrityBanner`, `progressCard`, `feedbackCard`.

### frontend/js/api.js
Every call to the server goes through `call()`. It adds the login token and fires a `vocalis:ai` event after AI calls so the top bar can update the request counter.

### frontend/js/app.js (the controller)
Grouped by sections marked with `// ======`:
- **Settings** (`loadOpts`, voice scoring `voiceScore`): time limit, languages, voices, saved in `localStorage`.
- **Navigation** (`show`): shows one screen, closes the calculator when leaving chat.
- **Upload and topics** (`handleUpload`, `renderTopics`, `startSession`).
- **Timer** (`startTimer`, `tick`): per-question countdown; at zero it sends *"[No answer: time ran out]"*.
- **Chat**: `addBubble`, `presentQuestion` (shows a diagram, opens the whiteboard), `send()` (bundles text, audio, drawing and the integrity counters).
- **Honesty guard**: *`box.addEventListener(ev, e => { e.preventDefault(); guard.paste++; ...`* and the `visibilitychange` listener counting tab switches.
- **Report**: `openReport` (score first, then `loadFull`), `renderIntegrity`, `renderFeedback` (predicted vs actual), `renderProgress` (SVG graph), `renderGaps` (tick-off cards), `loadFull` (report and notes with a retry button).
- **Downloads**: `downloadDoc` for the Word files.

### frontend/js/calc.js
Scientific calculator with its **own parser** (`evaluate`, recursive descent). It never calls `eval`, so typed text can only do maths. Handles degrees/radians, factorial, percent, implicit multiplication (`2pi`).

### frontend/js/whiteboard.js
Canvas whiteboard: pen, line, arrow, box, circle, mark-and-name, text, eraser, grid, axes, undo. `setDiagram(svg)` draws the AI's diagram underneath; `toBlob()` exports PNG for the server.

### frontend/js/speech.js, wav.js
`speech.js` wraps the browser's live speech recognition. `wav.js` converts a recording to 16 kHz mono WAV, which Gemini accepts reliably.

### frontend/js/orb.js
The animated maroon ribbon rings that move with the microphone volume (`ribbon`, `frame`).

### frontend/css/style.css
Maroon and black theme, 19px base font, outlined buttons (`--outline`), plus sections for the calculator, badges, progress card and feedback card.

### frontend/tests/e2e.js
Loads the real page in jsdom and clicks through register, upload, five answers, report, feedback, re-upload and logout (including the calculator and the paste block).

---

## Root files

| File | Role |
|---|---|
| `README.md`, `DEPLOY.md`, `docs/` | Judges' README, hosting steps, API reference, slide outline, demo script. |
| `check_gemini.py` | Tests your key and quota with one tiny request. |
| `check_integration.py` | Runs every offline test and reports READY or NOT READY. |
| `requirements.txt` | Server dependencies (Flask, google-genai, python-docx, gunicorn ...). |
| `Procfile`, `render.yaml` | Hosting on Render: `gunicorn --chdir backend app:app ...`. |
| `.env.example` | Settings: `GEMINI_API_KEY`, `GEMINI_MODEL`, `GEMINI_FALLBACK_MODELS`, `PUBLIC`, `DAILY_AI_LIMIT`. |
| `test-material/` | Sample PDF, PPTX, DOCX, scanned PDF used by tests. |
