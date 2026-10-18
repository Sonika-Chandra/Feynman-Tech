# Vocalis: learn it, say it, own it

> Draft README for the hackathon. Merge it with the existing `README.md` and replace the placeholders in [brackets].
> The six headings below are the ones the hackathon requires.

## Problem and user

**User:** a college student preparing for an exam from their own notes (slides, PDFs or Word files).

**Problem:** re-reading notes feels productive but gives a false sense of understanding. The Feynman technique
(explain it simply, find the gaps, go back to the source, simplify) fixes this, but students rarely have someone to explain to,
and nobody tells them which part of their explanation was wrong.

**Evidence:** [add a source for self-explanation or retrieval practice, and the result of a quick poll of 15-20 classmates].

## How it works

1. The student creates an account and uploads their notes. The backend reads PDF, PowerPoint, Word, text and image files and splits them into topics.
2. They pick a topic and the page turns into a chat. The AI "curious student" speaks first and asks question 1.
3. The student answers by voice or text (speech is transcribed in the browser, or by Gemini as a fallback). Each answer is compared with the notes
   and the AI asks one question about the biggest gap, for exactly five questions.
4. When a question needs a diagram, graph or calculation, a whiteboard opens. The student draws or labels with the mouse, pen or finger.
   Gemini looks at the picture and reads it as part of the answer, so it is questioned and scored like speech or text.
   For anatomy, circuits or flowcharts the AI can also draw a simple diagram with numbered parts for the student to name on the whiteboard.
   Optional per-question time limits, read-aloud questions and an accurate voice mode (Gemini re-transcribes the recording) are in the session settings.
5. The session is scored on accuracy, completeness, consistency and clarity (0-10 each) against a written rubric. The overall score is calculated in code.
6. The student gets a mistake report, a fact-check of their notes using Google Search, and notes in English or another language.
7. The gap report can be saved and uploaded again, so each past mistake becomes a topic to practise.

## Data and AI used

- **Data:** the student's own uploaded notes. Nothing is pre-loaded. Sample notes in `test-material/` were written by the team.
- **Model:** Google Gemini through the `google-genai` SDK, for questions, scoring, the report, notes and translation, and for
  reading whiteboard drawings, images, scanned PDFs and (as a fallback) audio.
- **Structured output:** Gemini replies in JSON that is validated with Pydantic. The overall score is computed from the four criteria in code.
- **Fact-check:** Gemini with Google Search grounding; findings are labelled "suspected" and come with source links.
- **Storage:** a local SQLite file holds accounts (passwords are hashed), uploads, conversations, whiteboard images and results.

## How to run it

```
git clone [repo url]
cd [repo]
python -m venv venv
venv\Scripts\activate            (Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env           (then put your Gemini API key in .env)
python check_integration.py      (free check; ends with READY TO COMMIT)
python backend/app.py
```
Open http://localhost:5000. Set `USE_FAKE_AI=1` in `.env` to try the whole app without using any Gemini requests.
Create an account on the first screen. Use Chrome or Edge for live speech recognition.

## AI tools and reused code

- **AI assistants used while building:** Claude (code and design help), GitHub Copilot, and Gemini (inside the product).
- **Libraries:** Flask and flask-cors, python-dotenv, Pydantic, google-genai, PyMuPDF, python-pptx, python-docx.
  Licenses differ (PyMuPDF is AGPL-3.0), so check them before any commercial use.
- **Browser features:** MediaRecorder, Web Audio and the Web Speech API.
- **Fonts:** Playfair Display and Manrope from Google Fonts.
- [List anything else the team copied, and from where.]

## Limits

- The score is an AI judgement against the student's own notes, not a measurement. It can be wrong or vary between runs.
- If the notes are wrong and the fact-check misses it, the app treats the notes as the truth.
- The free Gemini tier allows very few requests per day (about 20 per model in our tests), so long sessions need a paid key.
- PDF topics are found by a font-size heuristic and may be wrong for unusual layouts. Scanned PDFs and images depend on Gemini.
- Live speech recognition works in Chrome and Edge only. Other browsers fall back to server transcription.
- Translated notes (Kannada and others) have not been checked by a native speaker.
- Accounts are basic (email and password, tokens that never expire, no password reset) and SQLite is not designed for many simultaneous users.
- The AI reads whiteboard drawings with Gemini vision. Messy handwriting or tiny labels may be misread; the screen shows what it understood.
