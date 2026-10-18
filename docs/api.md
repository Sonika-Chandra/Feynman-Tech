# Backend API

Base URL: `http://localhost:5000`. All bodies are JSON unless stated. Errors are always `{"error": "readable message"}` with a matching HTTP status.

Every endpoint except `GET /`, `GET /health`, `POST /auth/register` and `POST /auth/login` needs the header
`Authorization: Bearer <token>`. The token comes from register/login. **It never expires**: it stops working only after `POST /auth/logout`.
Each user sees only their own uploads, sessions and drawings (other people's ids answer 404).

## Flow

```
register / login  ->  upload file  ->  start session (AI asks question 1)
  ->  answer (text / voice / whiteboard)  x5  ->  result  ->  report (download)  ->  upload the report again
```

## Accounts

| Call | Body | Returns |
|---|---|---|
| `POST /auth/register` | `{name, email, password}` (password at least 6 characters) | `201 {token, user:{id,name,email}}`; `409` if the email exists |
| `POST /auth/login` | `{email, password}` | `{token, user}`; `401` on wrong details |
| `GET /auth/me` | | `{user}` |
| `POST /auth/logout` | | `{ok: true}` and the token is deleted |
| `GET /sessions` | | `{sessions:[{session_id, topic, status, created_at, filename, overall}]}` newest first; `overall` is null until scored |

## Study material

`POST /upload` (multipart, field `file`; pdf, pptx, docx, txt, md, png, jpg, jpeg; up to 20 MB). A saved gap report (`.md`) is accepted too and becomes a list of topics.
Returns `201 {upload_id, filename, topics:[...], sections:[{title, preview}], characters}`.

## The conversation

**`POST /session/start`** `{upload_id, topic?}` (no topic = whole document). The AI speaks first:

```json
{"session_id": 7, "topic": "The Calvin cycle", "next_question": "In your own words, what happens in the Calvin cycle?",
 "needs_whiteboard": false, "diagram_svg": "", "round": 1, "total_rounds": 5}
```

`diagram_svg` is normally empty. For questions like "name the parts marked 1, 2 and 3" the AI draws a simple diagram; the backend cleans it
(only basic shapes survive, no scripts or links) and sends it here as an SVG string. The web app shows it behind the whiteboard so the student can mark and name its parts.
`needs_whiteboard` is always true when there is a diagram.

**`POST /session/answer`** sends one answer. Use `multipart/form-data` with any mix of these fields (at least one is required):

| Field | Meaning |
|---|---|
| `session_id` | required |
| `text` | typed (or browser-transcribed) answer |
| `audio` | a voice recording; transcribed by Gemini when `text` is empty. The topic's notes are sent along as a hint so technical terms are spelled correctly. |
| `drawing` | a PNG/JPEG of the whiteboard. The AI looks at it and writes what it sees; that description is saved as part of the answer and is used for the next question and the score. JSON callers may send a data URL in `drawing` instead. |

```json
{"next_question": "...", "needs_whiteboard": true, "diagram_svg": "<svg ...>", "round": 2, "total_rounds": 5, "should_stop": false,
 "transcript": "what the student said", "drawing_description": "A box labelled chloroplast with an arrow..." ,
 "session_status": "active"}
```

`needs_whiteboard` is true when the AI wants a diagram, graph or worked calculation. After the 5th answer `should_stop` is true,
`next_question` is empty and the session is `finished`. Answering a finished session returns `409`.

`POST /session/<id>/finish` ends a session early.
`GET /session/<id>` returns `{topic, status, round, total_rounds, messages:[{id, role, text, needs_whiteboard, has_drawing}]}` (used to resume a chat).
`GET /message/<message_id>/drawing` returns the saved whiteboard image.

## Results

`GET /session/<id>/result?mode=score|full&lang=Kannada`

- `mode=score`: one AI call. `{score:{scores:{accuracy,completeness,consistency,clarity:{score,justification}}, overall, mistakes, summary}}`.
- `mode=full` (default): adds `fact_check`, `report_markdown` and `notes`. If the AI cannot write the report, `report_markdown` is null and `report_error` says why (an error message is never stored as the report). It reuses a score that already exists, so the screen can show the score first and the gap report a moment later. The fact-check and notes never crash the call; on failure they carry an `error` string.

Results are cached per session.

`GET /session/<id>/report[?download=1]` returns the gap report as Markdown (`download=1` adds a download header).
Upload that file again with `POST /upload` to be tested on exactly those gaps.

## Other

`GET /health` returns `{status, fake_ai}`. `GET /` serves the web app from `frontend/`.
Set `USE_FAKE_AI=1` to run everything without Gemini.


## POST /tts  (login required)
Body `{"text": "...", "voice": "Aoede"}` -> `audio/wav` (Gemini text-to-speech, one request on `GEMINI_TTS_MODEL`).
In demo mode or when the quota is used up it returns 503 `{"error": ...}` and the page falls back to the device voice.

## GET /session/<id>/export?kind=gaps|full  (login required)
Word document download (`.docx`). `gaps` = detailed gap report (can be uploaded again to practise the gaps),
`full` = whole session report (scores explained, gaps, question-by-question feedback, conversation with drawings, fact-check, notes).
The result must exist first (open the report once). The result JSON now also contains `gaps`, `strengths`, `study_plan`, `question_feedback`.
