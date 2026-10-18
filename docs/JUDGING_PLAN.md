# Judging plan: score, deployment, limits, video

## 1. Maximising each criterion (weights from the rubric)

### Impact and relevance (25): "a clearly defined user, evidence the problem is real, a noticeable benefit"
- **Define one user in one sentence:** "A Class 11 to college student revising alone from their own notes, with no one to explain it to."
- **Show the problem is real.** Run a 5-question poll with 15 to 30 classmates *today* (Google Form): "How do you revise? Do you test yourself? Have you been surprised by an exam question you thought you knew?" One big number on slide 2.
- **Show the benefit with data from the app itself.** The new features give you the numbers:
  1. Confidence before vs real score ("You predicted 80, scored 55"). `GET /stats` reports how many students rated themselves 15+ points too high.
  2. Retry improvement ("6 of 8 retried topics improved, average +14"). The About page already shows these once students have used it.
  3. Usefulness rating from the feedback form.
- **Minimum pilot:** 8 to 10 people, each does one session, then a retry. Send them the public link. Screenshot the About page "What students found" card for slide 7.
- Cite the research on one line (Dunlosky 2013: practice testing and self-explanation beat re-reading).

### Innovation and creativity (20): "a fresh idea or useful twist, and a justified use of AI"
- Say it as a contrast: *chatbots answer you; Vocalis makes you answer.* The AI plays the curious student, so the learner is the teacher.
- Name the twists: whiteboard the AI reads, AI-drawn diagrams to label, gaps become the next test (closed loop), confidence calibration.
- **Justify AI:** a fixed quiz cannot find *your* gap or read a hand-drawn graph. Say what the AI does that rules cannot. Also say what is *not* AI: the score is computed in code, integrity checks are plain code.

### Technical implementation (25): "working main flow, sensible data and methods, evidence it works"
- The live demo must complete the full loop once, without edits or cuts.
- Slide with the architecture picture (flow at the top of `docs/CODE_GUIDE.md`) and three "sensible method" facts: structured JSON schemas, score computed in code, only missing report parts regenerated (quota-aware).
- **Evidence:** show the test run: `python check_integration.py` output with the passing tests, and the request-budget test ("one whole session costs 7 requests"). Say how many tests there are.
- Mention security choices briefly: sanitised SVG, no `eval` in the calculator, per-user ownership, daily cap.

### Usability and responsible use (15): "ease for the target user, clear explanations, careful data handling, accessibility"
- Ease: one-time key setup, one drop zone, dropdown topic, 5 questions. Mention first-time use takes under a minute.
- Accessibility: voice or typing, large text, optional timer, read-aloud, six languages for notes, keyboard operable.
- Responsible use slide (be specific): AI can be wrong, so every gap shows the student's own words next to the correction; notes belong to the user's account only; no data sold; integrity checks flag but a human decides; badges are not given for flagged sessions; a daily cap keeps the demo fair.
- Be honest that integrity checks are a deterrent, not proof (see section 3).

### Presentation and clarity (15): "clear demo video, coherent story, README that lets others run it"
- One story across everything: *problem -> Feynman technique -> Vocalis automates the listener -> evidence -> limits.* Use the same three words in README, slides, video and answers.
- README: fill every bracket placeholder; add the public URL and a screenshot at the top; "How to run" must work on a clean machine (test it once on a friend's laptop or a fresh folder).
- Video structure (4:30 max): 0:00 problem and user, 0:30 upload and topic, 1:00 two questions with voice and the whiteboard, 2:00 a math question with the calculator, 2:30 report (score, gaps, notes), 3:15 retry and the progress graph, 3:45 integrity flag shown deliberately, 4:00 evidence numbers, 4:20 limits and next step.
- Slides: max 8, big text, one idea each; follow `docs/slides-outline.md`.

## 2. Deployment steps (Render, free)
1. Push the code to your GitHub repo (the `vocalis-final` branch is merged into main). `.env` must **not** be committed.
2. Create a Gemini API key for yourself in AI Studio (aistudio.google.com) and run `python check_gemini.py` locally to confirm it works. The hosted site does **not** get a key: every visitor pastes their own.
3. render.com -> sign in with GitHub -> **New + -> Blueprint** -> pick the repo. Render reads `render.yaml`.
4. When asked, set `FEEDBACK_KEY` to a long random text (this is the **team key** for downloading feedback). Do **not** add `GEMINI_API_KEY`. Check `PUBLIC=1` and `PYTHON_VERSION=3.12.7`.
5. Wait for the deploy. Open `https://<name>.onrender.com/health`: it should show the model and `"status": "ok"`.
6. Open the site, create an account, click **API key** and paste yours, upload `test-material/photosynthesis.md`, run one whole session and one retry. Check the report opens and the Word download works.
7. Add the URL to `README.md` and `submission.md`. Then send it to your pilot students.
8. **Before judging:** open the site once to wake it (free plan sleeps after about 15 minutes), and make sure today's quota is not already spent.
9. If hosting fails, the project still counts: the public repo, README run steps and demo video are the required parts. The URL is optional.

Free-plan caveats to be aware of: data resets on restart, the quota is shared by everyone, the site sleeps when idle.

## 3. How to explain what Vocalis cannot do (do this on slide 8, in the README "Limits" section and in the video)

Say limits plainly, then give the mitigation. Judges reward honesty (responsible use) and distrust a project with no limits.

| Limit | How to say it |
|---|---|
| The AI can be wrong. | "Vocalis shows the student's own words beside every correction. Students should check against their textbook." |
| Scores come from one model's judgement, not a teacher's. | "Scores are computed from four fixed rubric criteria, which makes them consistent, but we have only compared them with a teacher on [N] sessions." Only claim what you measured. |
| Free quota: about 20 requests per model per day. | "A session costs 7 requests, so the free demo supports about two sessions per key per day. Fallback models and a per-user cap soften this; for real use we would enable billing." |
| Cheating cannot be fully prevented. | "We detect pasting, tab switching and copying from notes and flag the session, but a student can still read the notes on a phone. It is a deterrent and a signal for a teacher, not proof." |
| Topic quality depends on the notes. | "Poorly structured or handwritten notes produce weaker topics and questions." |
| Voice recognition varies by accent and browser. | "Accurate mode re-transcribes the recording with Gemini; typing always works." |
| Questions and reports are in English; only the notes are translated. | "Dictation works in five languages and the notes can be translated, but sessions are not yet fully Kannada." |
| Pilot is small. | "Our pilot had N students, which shows promise but is not a controlled study." |
| Not built yet. | Teacher dashboard, spaced-repetition reminders, long-term accounts and storage on the free host. |

## 4. Recording the video without triggering the cheating checks

What the checks look at: a **blocked paste or drop** into the answer box, the page becoming **hidden** (switching browser tab, minimising the window, or locking the screen) while you are in a chat, and answers that **copy 6-word runs from the notes**. Clicking another window does not count unless the page becomes hidden.

Do this:
1. **Use a recorder that does not switch pages.** On Windows press **Win + G** (Xbox Game Bar) or use OBS or the built-in Snipping Tool recording, then start recording *before* you open the chat. Starting or stopping the recording from the same page is fine. Do not alt-tab to a notes document mid-session.
2. **Keep everything in one browser tab** and put your script on a **second device or phone**, or print it. Do not paste from a script. Type the answers or speak them. Typing short answers in your own words is faster than it sounds.
3. **Answer in your own words.** Do not read sentences straight from the notes: that triggers the copy check. Paraphrase.
4. **Record the demo with a fresh account** so history is clean and the earlier practice does not flag the real run.
5. **Do the flag demo on purpose, as a feature.** Near the end, start one extra short session, press Ctrl+V in the answer box (it is blocked and toast-warned), switch tabs three times, then open the report to show the red "not independent work" banner and the missing badge. This shows judges the integrity system works, and it is honest.
6. **Do one rehearsal** end to end first. Check the report shows a badge, not "Flagged".
7. If you do trigger it by accident, that session is simply flagged; start a new account and record again. Do not edit the database.

Do not try to disable the checks for the recording. If a judge opens the code, a hidden bypass would look worse than a flag.
