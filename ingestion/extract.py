"""
The single entry point used by the backend:   extract(path) -> [{"title": str, "text": str}, ...]
Picks the right reader from the file extension. Every problem is raised as ExtractionError
with a message that can be shown to the student.
"""
import os

from . import docx_reader, image_reader, pdf_reader, pptx_reader, report_parser, topics
from .errors import ExtractionError

SUPPORTED = {".pdf", ".pptx", ".docx", ".txt", ".md", ".png", ".jpg", ".jpeg"}
MIN_CHARS = 30


def _read_text_file(path):
    raw = open(path, "rb").read()
    for enc in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


def extract(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".doc":
        raise ExtractionError("Old .doc files are not supported. Save it as .docx and upload it again.")
    if ext == ".ppt":
        raise ExtractionError("Old .ppt files are not supported. Save it as .pptx and upload it again.")
    if ext not in SUPPORTED:
        raise ExtractionError(f"File type '{ext}' is not supported. Use: {', '.join(sorted(SUPPORTED))}.")

    try:
        if ext == ".pdf":
            sections = pdf_reader.read(path)
        elif ext == ".pptx":
            sections = pptx_reader.read(path)
        elif ext == ".docx":
            sections = docx_reader.read(path)
        elif ext in (".png", ".jpg", ".jpeg"):
            sections = image_reader.read(path)
        else:
            text = _read_text_file(path)
            sections = report_parser.to_sections(text) if report_parser.is_report(text) else topics.split_sections(text)
    except ExtractionError:
        raise
    except Exception as e:  # noqa: BLE001
        raise ExtractionError(f"Could not read this {ext} file ({type(e).__name__}).") from e

    sections = topics.finalize(sections)
    if sum(len(s["text"]) for s in sections) < MIN_CHARS:
        raise ExtractionError("Could not find enough readable text in this file.")
    return sections
