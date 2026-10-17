# API contract (backend by P3)

Base URL: `http://localhost:5000`. Every error is JSON: `{"error": "message"}` with a matching HTTP status.
All answers are sent as text; audio is optional and converted to text by the server.

## Flow

1. `POST /upload` -> `upload_id` and `topics`
2. `POST /session/start` -> `session_id`
3. `POST /session/answer` (repeat) -> next question, until `should_stop` is true
4. `GET /session/<id>/result` -> scores, report, notes
5. `GET /session/<id>/report` -> the Markdown report (download)

## Endpoints

| Method and path | Send | Returns |
|---|---|---|
| `GET /health` | nothing | `{"status": "ok", "fake_ai": false}` |
| `POST /upload` | form field `file` (pdf, pptx, docx, txt, md, png, jpg; max 20 MB) | 201 `{"upload_id", "filename", "topics": [...], "characters"}` |
| `POST /session/start` | JSON `{"upload_id": 1, "topic": "optional topic name"}` | 201 `{"session_id", "topic", "prompt_to_student"}` |
| `POST /session/answer` | JSON `{"session_id": 1, "text": "..."}` **or** form fields `session_id` + file field `audio` | `{"next_question", "should_stop", "round", "transcript", "session_status"}` |
| `POST /session/<id>/finish` | nothing | `{"session_id", "session_status": "finished"}` (student ends early) |
| `GET /session/<id>/result?mode=full&lang=Kannada` | `mode`: `full` (default) or `score` (score only, 1 AI call); `lang` for the translated notes | The result object below. Computed once, then cached. |
| `GET /session/<id>/report?download=1` | nothing | Markdown text; `download=1` adds a download header. 404 until `/result` has been called. |
| `GET /session/<id>` | nothing | `{"session_id", "topic", "status", "messages": [{"role", "text"}]}` |

## Answer response

```json
{"next_question": "Where does this happen?", "should_stop": false, "round": 1,
 "transcript": "what the student said", "session_status": "active"}
```
When `should_stop` is true, `next_question` is `""` and the session is finished: call `/result`.
Answering a finished session returns 409.

## Result object

```json
{
  "score": {
    "scores": {
      "accuracy":     {"score": 7, "justification": "..."},
      "completeness": {"score": 6, "justification": "..."},
      "consistency":  {"score": 9, "justification": "..."},
      "clarity":      {"score": 8, "justification": "..."}
    },
    "overall": 75,
    "mistakes": ["..."],
    "summary": "..."
  },
  "fact_check": {"findings": "...", "sources": [{"title": "...", "url": "..."}]},
  "report_markdown": "# Mistake Report ...",
  "notes": {"language": "Kannada", "notes": "...", "notes_translated": "..."}
}
```
With `mode=score`, `fact_check`, `report_markdown` and `notes` are `null`.
Each score is 0-10, `overall` is 0-100.

## Frontend example (P2)

```javascript
const API = "http://localhost:5000";

// upload
const form = new FormData();
form.append("file", fileInput.files[0]);
const up = await (await fetch(`${API}/upload`, { method: "POST", body: form })).json();

// start
const s = await (await fetch(`${API}/session/start`, {
  method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ upload_id: up.upload_id })
})).json();

// text answer
const a = await (await fetch(`${API}/session/answer`, {
  method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ session_id: s.session_id, text: "my explanation" })
})).json();

// audio answer (a Blob from MediaRecorder)
const f2 = new FormData();
f2.append("session_id", s.session_id);
f2.append("audio", audioBlob, "answer.webm");
const a2 = await (await fetch(`${API}/session/answer`, { method: "POST", body: f2 })).json();
```

## Notes for the team

- Until P4's `ingestion/extract.py` exists, only `.txt` and `.md` uploads work. P4's `extract(path)` must return a list of `{"title": str, "text": str}` (or one string).
- Audio: the server sends the recording to Gemini. Gemini's documented formats are WAV, MP3, AIFF, AAC, OGG and FLAC. Browsers often record WebM, which may be rejected. If that happens, P2 or P4 should convert or record in a supported format. Typed answers always work.
- `USE_FAKE_AI=1` makes the whole API work with canned AI replies and no quota, for building and testing the frontend.
- `/result?mode=full` makes about 5 AI calls. Use `mode=score` while testing to save quota.
