# Vocalis: teach it to learn it

An AI study partner built on the **Feynman technique**. You upload your own notes, explain a topic out loud (or in writing, or on a whiteboard)
to a curious AI "student", and it questions you until your gaps show. You finish with a score, a detailed gap report and revision notes,
and you can feed the gap report back in to practise exactly what you got wrong.

> Craft N Code Karnataka 2026 · Theme: AI for Education · Team: **[team name]** · [member names]
>
> **Live demo:** [deployed URL, or "run locally, see below"] · **Demo video:** [link] · **Slides:** [link]

## Problem and user

**User:** a college or senior-school student revising for an exam from their own notes (slides, PDFs, Word files, photos of handwritten pages).

**Problem:** re-reading notes feels productive but gives a false sense of understanding. Psychologists call this the
[illusion of explanatory depth](https://en.wikipedia.org/wiki/Illusion_of_explanatory_depth): people rate their understanding highly until they are asked to
explain something step by step (Rozenblit & Keil, 2002). A large review of study techniques
([Dunlosky et al., 2013](https://www.psychologicalscience.org/journals/pspi/1529100612453266/)) found that re-reading and highlighting have low utility,
while practice testing and self-explanation work much better.
The Feynman technique (explain it simply, find the gaps, go back to the source, simplify) uses exactly this, but it needs a listener who asks good questions,
and most students study alone. Students also rarely get a clear list of *which* parts of their explanation were wrong.

**Our evidence from students:** [poll result, e.g. "14 of 18 classmates re-read their notes and only 3 ever explain them aloud"]. See *Evidence that it works* below for what students did with Vocalis.

**Benefit:** the student gets a patient listener at any hour, in their own notes' vocabulary, and leaves with a concrete list of gaps and a way to re-test them.
It also works in the student's language: dictation in English, Hindi, Kannada, Tamil or Telugu, and revision notes translated into Kannada, Hindi, Tamil, Telugu or Malayalam.

## How it works

1. **Upload.** The student creates an account, pastes their own free Gemini API key (the **API key** button; it stays in their browser) and uploads notes: PDF, PowerPoint, Word, text, Markdown or an image. The backend extracts the text
   (OCR through Gemini for scans and photos) and splits it into numbered topics with clear headings.
2. **Choose a topic and settings.** Optional time limit per question, speech language, accurate voice mode and read-aloud with Aoede, the Gemini AI voice. When read-aloud is on, the answer box opens and the countdown starts only after Aoede has finished the question.
3. **The AI asks first.** The page turns into a full-screen conversation. The AI plays a curious student and asks exactly **five** questions, each one following the previous answer
   and aimed at the biggest gap. It never gives the answer.
4. **Answer in any way.** Type, speak (live transcript plus an optional accurate re-transcription by Gemini), or use the **whiteboard** for maths, graphs and diagrams.
   For anatomy, circuits or flowcharts the AI draws a detailed diagram with numbered parts for the student to name; Gemini looks at the student's marks and reads them as part of the answer.
5. **Scoring.** An examiner prompt scores accuracy, completeness, consistency and clarity (0 to 10 each) against the notes only; the overall score (0 to 100) is calculated in code, not by the model.
6. **Reports.** The student gets a gap report (what was said, what was wrong, the correct explanation, why it matters, how to fix it, a practice question), 
   (flagged as *suspected*, with sources), revision notes, and a study plan. The **gap report** and the **revision notes** (with the translation) can each be read on the page and downloaded as separate Word files.
7. **See your improvement.** Retrying a topic draws a graph of your scores per attempt and per criterion (from saved results, no extra AI request).
8. **Honest practice.** Pasting is blocked and counted, leaving the page is counted, and answers copied word-for-word from the notes are detected on the server (no AI request). A flagged session is labelled and earns no badge.
9. **Badges.** Bronze 40+, silver 60+, gold 80+, platinum 90+, plus Improver, Honest scholar and others, shown on the report and on the home page.
10. **Built for the time limit.** The chosen time per answer is sent to the AI so questions fit it. Maths topics get numerical and graph questions, and a scientific calculator opens next to the whiteboard.
11. **Confidence check and feedback.** Before the test the student rates how well they think they know the topic; the report then shows "you predicted 80, you scored 55" and asks how useful the session was and how confident they feel now.
12. **Feedback you can compile.** The report asks for a usefulness rating, confidence after the test and quick tags. The About page shows the totals, and `/feedback/export.csv` downloads every response (anonymous) for your evidence slide.
13. **Close the loop.** The gap report can be uploaded again: every gap becomes a topic to practise.

```
 notes -> extract + split -> pick topic -> AI asks Q1 ... Q5 (voice / text / whiteboard)
                                                   |
        gap report <- scores + gaps + notes <-+
              \----------- upload again ------------> new session on the gaps
```

## Evidence that it works

- **Automated tests (no API key needed):** `python check_integration.py` runs the AI-logic tests (including a check that a whole session costs exactly 8 Gemini requests), the API tests, the full-loop test, the extraction tests on PDF, PowerPoint, Word, image and report files, and a browser-flow test. [add: "N tests, all passing"].
- **Test files with known answers:** `test-material/pairs/` holds a correct and a deliberately wrong version of a PDF, a Word file, a PowerPoint and a flowchart image, with `ANSWER_KEY.md` listing every planted error, so you can check how the AI handles notes that contain mistakes.
- **Pilot with students:** [N students, date, how they were recruited]. Results come from the app itself (`/stats`, also shown on the About page): [average score change between first and second attempt], [how many rated their confidence 15+ points above their real score], [average usefulness rating out of 5]. Be exact; say this is a small pilot, not a controlled study.
- **Live run:** [screenshot of one real session on the hosted site].

## Data and AI used

- **Data:** only what the student uploads. No pre-loaded dataset. The sample notes in `test-material/` were written by the team.
- **Model:** Google Gemini through the `google-genai` SDK, for the questions, scoring, gap report, notes, translation, whiteboard understanding (vision), OCR, diagram drawing,
  transcription and text-to-speech.
- **Structured output:** Gemini replies as JSON validated with Pydantic, so the app never parses free text for scores. The grader runs at low temperature for consistency.
- **Browser features:** Web Speech API (live transcript), MediaRecorder and Web Audio (the volume-reactive orb).
- **Storage:** SQLite for accounts (passwords hashed), uploads, conversations, whiteboard images and results.
- **Why AI is justified:** questions must adapt to what the student actually said and to the specific notes, drawings must be understood, and gaps must be explained in context.
  A fixed quiz bank cannot do any of these.

## How to run it

Needs Python 3.10 or newer.

```
git clone https://github.com/Sonika-Chandra/Feynman-Tech.git
cd Feynman-Tech
python -m venv venv
venv\Scripts\activate            # Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
copy .env.example .env           # Mac/Linux: cp .env.example .env
```

Edit `.env`:
- **Your own key on the site (default):** leave `GEMINI_API_KEY` out of `.env`. Open the app, click **API key** and paste a free key from aistudio.google.com/apikey.
- **Or a server key:** `GEMINI_API_KEY=...` in `.env` (a placeholder like `your_key_here` is ignored). `python check_gemini.py` tells you whether it and its quota work.

```
python backend/app.py
```

Open **http://localhost:5000** in Chrome or Edge (live speech recognition works there). Create an account, then upload `test-material/photosynthesis.md`.

**Checks that need no API quota:** `python check_integration.py` (file list, interfaces, AI logic tests, API tests with a stand-in AI, extraction tests on sample files).
An optional browser-flow test is in `frontend/tests/`.

**Hosting it publicly:** see [DEPLOY.md](DEPLOY.md). The hosted version sets `PUBLIC=1` and a daily request cap per user so the free AI quota is shared fairly.

## AI tools and reused code

- **AI assistants used while building:** Claude (Anthropic) was used as a pair-programming assistant for much of the code, tests and documentation; GitHub Copilot [if used]; Gemini inside the product.
  The team reviewed, ran and tested the result. [Adjust this paragraph to describe who did what.]
- **Open-source libraries:** Flask, flask-cors, python-dotenv, Pydantic, google-genai, PyMuPDF (AGPL-3.0), python-pptx, python-docx, gunicorn. Fonts: Playfair Display and Manrope (Google Fonts).
- **Reused code:** no code copied from other projects. [Mention anything a teammate adapted from a tutorial.]

## Limits

- **AI can be wrong.** Questions, scores and the gap report come from a language model. Scores are a study aid, not a grade. Vocalis does not fact-check your notes: if your notes are wrong, the AI marks you against them, so check them against your textbook.
- **Diagrams and drawings vary.** The AI-drawn diagrams are good for common textbook subjects but can be imperfect, and handwriting recognition depends on how clearly the student writes.
- **Feedback and impact.** Rating each session is required (one tap on the stars). The **Impact** page (`/#impact`) charts the anonymous results live: score spread, weakest criterion, usefulness, would-recommend, confidence before vs real score, gains on retry, badges and flagged sessions. The CSV for the team is at `/feedback/export.csv?key=...`.
- **Free-tier quota.** Gemini's free tier allows only a limited number of requests per day (about 20 per model). One full session (5 questions, score, report, notes and translation) costs **7 requests**, so a run plus a test on your gaps (14) fits in one day. Whiteboard drawings, accurate voice mode and the AI voice cost 1 request each. The top bar shows the running count, and the hosted demo caps each user.
- **Browsers.** Live speech recognition needs Chrome or Edge. Microphone access needs HTTPS or localhost.
- **Privacy.** Notes and answers are sent to Gemini to be processed; do not upload confidential material. Accounts are simple (email and password; the address is not verified). Each visitor's Gemini key is kept in their own browser and sent with their requests over HTTPS; the server uses it for that request only and never saves or logs it. Login tokens do not expire until log out, which suits a demo and should be shortened for production.
- **Cheating checks are a deterrent.** Pasting is blocked, tab switches and answers copied from the notes are flagged, but a student can still read their notes on another device. A flag is a signal for a teacher, not proof.
- **Small pilot.** Our student results come from [N] people and show promise, not proof.
- **Scale.** SQLite and one server process are fine for a demo or a class, not for thousands of users.
- **Not built yet:** teacher dashboard, fully Kannada questions and reports, spaced-repetition reminders.

## Team

[Name, role] · [Name, role] · [Name, role] · [Name, role]
