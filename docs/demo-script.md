# Vocalis demo: what to do and what to say

Target about 4:50, never over 5:00. Read the lines in the “Say” column in your own words; they are written to be spoken, not memorised. Replace the [square brackets] with your real numbers from the Impact page.

## Before you record

- Use a fresh Gemini key with unused quota (a full session is 7 requests, a retest another 7, the AI voice about 1 per question). Check it with `python check_gemini.py`.
- Rehearse the whole thing once with the same key. The key box, the quota card and the voice are all part of the product, so a hiccup is fine if you know the recovery lines (last section).
- Open the live site (not localhost) a few minutes early so the free plan is awake. Browser zoom 100%, other tabs closed, notifications off, microphone allowed.
- Keep ONE browser tab on Vocalis during every session. Leaving the page three times, or pasting once, flags the session and removes the badge. Do not alt-tab to read this script; print it or put it on a second device.
- Type your own answers. Never paste, and do not copy sentences from the notes (6 matching words in a row counts as copying).
- Have `test-material/photosynthesis.pdf` ready, and the pilot numbers open on `/#impact` in a second window recorded separately or screenshotted.
- Turn on Read questions aloud (Aoede) and pick a 60-second time limit before you record. Expect a few seconds before Aoede starts each question; the box stays locked until she has finished, so do not click around while you wait.

## The 4:50 demo

| Time | On screen / do | Say |
|---|---|---|
| 0:00–0:25 | Login page. Stay on it while you speak. | Students re-read their notes and feel confident, but feeling confident and understanding are different things. The Feynman technique says you only understand something if you can explain it simply. Vocalis is an AI student that listens to you explain a topic and keeps asking questions until the gaps show. It is built for students in Karnataka and anywhere else who study from notes, slides and textbooks. |
| 0:25–0:45 | Click Create account, register, you land on Home. Click the 🔑 API key button. | I make an account. Vocalis uses Google’s Gemini, and every student brings their own free key, so nobody shares a quota and we never store it. It lives only in this browser. That is also how the app stays free to run for a whole class. |
| 0:45–1:15 | Drop in photosynthesis.pdf. Open the topic dropdown, choose “The Calvin cycle” (or Whole document). Drag the confidence slider to about 8. Set time limit 60 s. Tick Read questions aloud. Click Start. | I upload my own notes: PDF, PowerPoint, Word, text, even a photo of a flowchart. It finds the topics, and I choose the one I want to be tested on. Before I start, I rate how confident I am out of ten. That matters later. I add a 60-second limit per question, and Aoede, the AI voice, will read each question to me. |
| 1:15–1:50 | Question 1 appears and Aoede reads it; the answer box is locked until she finishes. Point at the box unlocking and the countdown bar appearing. Answer in 3–4 own sentences and leave one detail out on purpose. Send. | The AI speaks first, like an examiner at a viva. The box unlocks only when Aoede has finished the question, and that is when my countdown starts, so the reading never eats into my time. I explain it as if teaching a beginner, and I will deliberately leave one detail out. There are five questions and each one follows what I just said. |
| 1:50–2:20 | Question 2 is a diagram question: the whiteboard opens with a labelled diagram. Use Mark & name on two numbered parts, add an arrow. Send. | When a question needs a picture, the whiteboard opens. Here the AI drew a diagram and I name the numbered parts. The AI looks at my drawing and tells me how it read it, and that counts as part of my answer. For maths and physics it asks numeric and graph questions too, and there is a scientific calculator built in. |
| 2:20–2:35 | Open the calculator for two seconds, type 6*12/2, close it. Then answer the remaining questions quickly (cut or speed up in editing). | Here is the calculator. I will answer the last three questions quickly. After the fifth question the conversation ends and goes straight to marking. |
| 2:35–3:20 | Report loads. Point at: score ring, badge chip, four metric bars. Click Gaps tab, open the first gap card. Then click Revision notes tab and show the Kannada section. Show the two Word download buttons. | My score is out of 100, built from four marks out of ten: accuracy, completeness, consistency and clarity. The total is calculated in code, not by the AI. I earn a badge from the score. The Gaps tab lists exactly what I got wrong: what I said, the correct explanation from my own notes, why it matters and a question to test myself. The revision notes cover only the parts I struggled with, and can be translated into Kannada, Hindi, Tamil, Telugu or Malayalam. Both reports download as Word files. |
| 3:20–3:45 | Click Test me on my gaps, or Try this topic again. In the retry, press Ctrl+V once to paste (this is the deliberate flag). Skip ahead in editing to the new report: show the red banner “not independent work”, then the progress graph if the scores differ. | Every gap becomes the next test, so I practise exactly what I got wrong, and a progress graph tracks my attempts. To keep it honest, pasting, copying from the notes and leaving the page are counted. I pasted on purpose: the session is flagged, no badge, and the report says why. |
| 3:45–4:05 | Scroll to the feedback card. Tap four stars with the mouse (it saves at once), tap Yes, move the confidence-after slider. | Rating the session is required, one tap, so our numbers are not only from happy users. I also say how confident I feel now. Compared with the confidence I gave at the start and the score I actually got, that shows whether students judge their own understanding correctly. |
| 4:05–4:30 | Click Impact in the top bar (or open /#impact). Pause on the tiles, then the confidence chart and the retry chart. | This is what students found in our pilot with [N] students and [S] sessions. The average score was [A]. They rated it [U] out of 5. [X] of [Y] retried topics improved, by [G] points on average. And [P] percent felt more sure than they scored, which is the illusion of knowing that explaining out loud exposes. All of this is anonymous. |
| 4:30–4:48 | Back to the home screen or the About page. | Limits, honestly: the AI can be wrong, scores are a study aid, we do not fact-check your notes, and free Gemini quota is limited, which is why each student brings a key. Next: more subjects and teacher dashboards. Thank you. |

## If someone asks you to explain the project live (60 seconds)

- **Problem and user.** Students study by re-reading, which creates a false feeling of understanding. Our users are school and college students who study from notes and slides, especially those without a tutor to question them.
- **What it does in one line.** You teach an AI student out loud; it asks follow-ups until your gaps show, then gives you a report and the next test.
- **Why it is different.** Closed loop: gaps from one report become the next test. It reads whiteboard drawings and flowchart photos. It compares your confidence with your real score. It is honest about integrity.
- **How it works.** Flask and SQLite back end, a plain HTML/JS front end. Gemini with structured JSON for questions and scoring, vision for drawings and flowcharts, text-to-speech (Aoede) for reading questions. Score is computed in code from four criteria. Seven Gemini requests per full session.
- **Responsible use.** Bring-your-own-key, so no shared quota and no stored keys. Anonymous impact data. Integrity flags are a deterrent and are shown to the student with the reasons. Marks come only from the student’s own notes, so wrong notes give wrong marking: students should check them against a textbook.

## Questions judges may ask

- **Does it check my notes are correct?** No. We removed the fact-check on purpose, because a model can be confidently wrong. It marks you against your notes, and we say so.
- **Can students cheat?** Pasting is blocked and counted, copying 6+ words in a row from the notes is detected, and leaving the page 3 times flags the session. Flagged sessions get no badge and are left out of our numbers. It is a deterrent, not proof.
- **What happens when the quota runs out?** A box opens asking for a new key, their answers are saved, and as soon as the new key works the same step runs again. They can also reopen the session from Continue on the home screen.
- **What data do you keep?** Accounts, uploads, answers and results in the server database. The Gemini key stays in the browser. The Impact page shows only anonymous totals.
- **How do you know it helps?** The pilot numbers on the Impact page: scores on retry, confidence versus score, and usefulness ratings. We are honest that it is a small pilot.
- **Why Gemini?** Structured JSON output, vision for drawings and flowcharts, speech output and a free tier students can use with their own key.
- **What would you build next?** More languages for questions, offline use, teacher dashboards, spaced reminders for the gaps.

## When something goes wrong during the demo

- **The voice is slow or silent.** Say: “Aoede takes a few seconds to prepare each question, and the box opens when she finishes.” There is no time limit on her. If she is still not ready after 20 seconds a Skip reading button appears. If Aoede fails (for example out of quota) a message says so and the box opens so you can read the question on screen.
- **The key box or the quota card appears.** Say: “That is the quota flow: my answers are saved, I paste another key, and it carries on.” Paste a spare key from another Google account. This is a feature, so keep it in the video if it happens.
- **An AI error card appears.** Read the card aloud, close it and press the same button again. If it keeps failing, stop and record the remaining parts from a second key.
- **The site is asleep.** The first load can take about a minute on the free plan. Open it before you start recording.
- **You pasted by accident.** That session is flagged. Start another session; the flag belongs to the one session only.

## Team access to the Impact data

- Impact page (public, anonymous charts): https://YOUR-SITE.onrender.com/#impact. No login needed. Locally: http://localhost:5000/#impact.
- To add up only a period (say a 3-hour pilot): on the Impact page pick Last 3 hours, or set From and To (your own time zone). The charts and the CSV download both follow that window. In a URL: /insights?hours=3 and /feedback/export.csv?key=THE_TEAM_KEY&hours=3.
- Chart data as JSON: https://YOUR-SITE.onrender.com/insights.
- Full feedback spreadsheet (with comments): open the Impact page, type the team key into the “Team key” box and press Download feedback (CSV). Or open https://YOUR-SITE.onrender.com/feedback/export.csv?key=THE_TEAM_KEY.
- The team key is the FEEDBACK_KEY value you typed in Render (Dashboard → your service → Environment). Share it only inside the team. Locally, with no key set, the CSV opens without it.
- Download the CSV and screenshot the Impact page before every redeploy: the free plan wipes the database when the server restarts.
