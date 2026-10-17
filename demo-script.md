# Demo script (target 3:30, hard limit 4:00)

## Before you start (check once)
- VS Code open at the project, terminal shows (venv), run `cls`
- `.env` has the key, internet works
- `test-material/flowchart.png` open in a tab
- Commands below pasted in a Notepad file, ready to copy
- Backup: screenshots of each output, in case Gemini is slow

## 0:00 - 0:20  The problem  [speaker: ___]
Students think they understand a topic but cannot explain it.
Our app asks them to explain it and scores the answer.

## 0:20 - 1:10  Documents in, clean sections out  [P4]
Say: "Study files come in many formats. We turn them into one format."
Run: `python ingestion\extract.py test-material\master.pdf`
Show: the list of sections with title, text and topic.
Run: `python ingestion\extract.py test-material\master.docx`
Say: "Same format for Word, and the same for PowerPoint."
Run: `python ingestion\extract.py test-material\master.pdf | Select-String "2015"`
Say: "We keep a planted error on purpose. The fact-checker must find it."

## 1:10 - 1:50  Audio  [P4]
Say: "Students can also speak. Gemini turns the recording into text."
Run: `python ingestion\extract.py test-material\Noisy.m4a.mp4`
Show: the transcript. Say it kept noise and accent with no word errors.
(While it loads, 5-15 sec, explain what Gemini is doing.)

## 1:50 - 2:15  Flowchart  [P4]
Show: flowchart.png in the editor tab.
Run: `python ingestion\extract.py test-material\flowchart.png`
Show: the 5 numbered steps. Say: "Images become text steps too."

## 2:15 - 3:10  The explain session  [P2 / P3 / P1]
[Open the app, upload a file, pick a topic, answer by mic or text,
show the AI follow-up question.]

## 3:10 - 3:40  Score and mistake report  [P1 / P2]
[Show the four scores, then the report. Show that the fact-checker
found the planted errors: James Gosling, 2015, "compiled".]

## 3:40 - 4:00  Close  [speaker: ___]
AI tools we used: Claude, Gemini [and Copilot if used].
Limits: scanned PDFs are not built yet.