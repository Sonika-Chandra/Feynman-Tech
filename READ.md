# Feynman Explain App

## 1. Problem and user
[Team: confirm this in one or two sentences.] Students often feel they
understand a topic but cannot explain it. This app lets a student upload
study material, choose a topic and explain it by voice or text. The AI
asks follow-up questions, scores the explanation and writes a report of
the mistakes.

## 2. How it works
1. The student uploads a PDF, PPTX, DOCX, audio clip or flowchart image.
2. Ingestion (`ingestion/extract.py`) turns the file into a list of
   sections. Each section has a `title`, `text` and `topic`.
3. The student picks a topic and starts a session (mic or text).
4. [P1: one line on the question loop and scoring.]
5. The student sees four rubric scores and a mistake report.

## 3. Data and AI used
- Our own sample files in `test-material/`, with 3 planted errors
  (listed in `test-material/NOTES.md`).
- Gemini: audio transcription and flowchart reading in ingestion.
  [P1: add the question, scoring and fact-check use.]
- Libraries: PyMuPDF (PDF), python-pptx (slides), python-docx (Word),
  google-genai (Gemini), python-dotenv (keys).

## 4. How to run it
Needs Python 3.10 or newer and a Gemini API key from
https://aistudio.google.com
```
git clone [repo link]
cd [repo folder]
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```
Copy `.env.example` to `.env` and set `GEMINI_API_KEY=your_key`.
Start the app: [P3: server command]. Open the app: [P2: how].

Test ingestion alone:
```
python ingestion/extract.py test-material/master.pdf
```
It works the same for `.docx`, `.pptx`, audio files and `.png` flowcharts.

## 5. AI tools and reused code
- **Claude:** used for step-by-step help writing the DOCX, PPTX and PDF
  extractors, the PDF cleaning functions, topic tagging, the audio and
  flowchart scripts, and the `extract.py` entry point. Also used to debug
  setup errors. I ran and
  tested all code myself.
- **Gemini:** runs inside the app for audio transcription and flowchart
  reading (model: gemini-3.5-flash). The calls follow Google's public
  Gemini API examples.
- **GitHub Copilot:** not used.
- **Reused code:** PyMuPDF, python-pptx, python-docx, google-genai and
  python-dotenv libraries.

## 6. Limits
- Scanned (image-only) PDFs have no text. The plan is to send them to
  Gemini Vision, but this is not built yet.
- Sections come from headings or font size. Files with no headings give
  one "Untitled" section.
- Audio was tested with moderate noise and an accent, and both gave a
  100% word match. Loud or fast speech is not tested yet.
- Ingestion keeps mistakes as written. It does not fix facts.                                                     -The flowchart reader was tested on flowchart image only.