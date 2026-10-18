"""Images (flowcharts, diagrams, photos of notes) and scanned PDFs -> text, using Gemini vision."""
import os

from ._llm import ask, fake_mode, part
from .errors import ExtractionError

MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}

IMAGE_SYSTEM = """You convert an image of study material into plain text for a student.
- If it is a FLOWCHART or process diagram: write it as numbered steps in order. Write each decision as
  'If <question>: yes -> go to step X; no -> go to step Y'. Use the exact labels shown in the image.
- If it is a photo or scan of printed or handwritten notes: transcribe it faithfully, keeping headings on their own lines.
- If it is any other diagram: explain what it shows in short, plain sentences, using the labels in the image.
Output only the resulting text, with no commentary."""

OCR_SYSTEM = """You extract text from a scanned document. Keep the original wording. Put each heading on its own
line starting with '# '. Separate paragraphs with a blank line. Output only the text, with no commentary."""


def read(path):
    ext = os.path.splitext(path)[1].lower()
    if ext not in MIME:
        raise ExtractionError("This image type is not supported. Use PNG or JPG.")
    with open(path, "rb") as f:
        data = f.read()
    name = os.path.basename(path)
    fake = (f"1. Start with the study material in {name}.\n2. Explain the first main idea.\n"
            "3. If the idea is clear: continue to step 4; otherwise go back to step 2.\n4. Finish with a summary.")
    text = ask([part(data, MIME[ext]), "Convert this image to study text."], IMAGE_SYSTEM, fake)
    if len(text) < 20:
        raise ExtractionError("Could not read any text or steps from this image. Try a clearer picture.")
    return [{"title": "Image: " + os.path.splitext(name)[0][:60], "text": text}]


def ocr_pdf(path):
    """Scanned PDF -> text (one Gemini request)."""
    with open(path, "rb") as f:
        data = f.read()
    fake = "# Scanned document\n\nThis is placeholder text from a scanned PDF in fake mode, long enough to pass the check."
    text = ask([part(data, "application/pdf"), "Extract the text of this document."], OCR_SYSTEM, fake)
    if len(text) < 30:
        raise ExtractionError("This PDF has no readable text, even after scanning it. Try a clearer copy.")
    return text
