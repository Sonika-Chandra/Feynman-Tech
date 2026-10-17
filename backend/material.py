"""
Turns an uploaded file into text sections.
Uses P4's ingestion/extract.py when it exists:   extract(path) -> list of {"title": str, "text": str}  (or a plain str)
Until then, only .txt and .md files work.
"""
import os


class ExtractionError(Exception):
    pass


def _normalise(result):
    if isinstance(result, str):
        result = [{"title": "Whole document", "text": result}]
    sections = []
    for item in result or []:
        if isinstance(item, str):
            item = {"title": f"Section {len(sections) + 1}", "text": item}
        title = str(item.get("title") or f"Section {len(sections) + 1}").strip()
        text = str(item.get("text") or "").strip()
        if text:
            sections.append({"title": title, "text": text})
    return sections


def load_sections(path):
    try:
        from ingestion.extract import extract
    except ModuleNotFoundError as e:
        if (e.name or "").split(".")[0] != "ingestion":
            raise                      # a real missing package inside P4's code: show it
        extract = None

    if extract:
        return _normalise(extract(path))

    ext = os.path.splitext(path)[1].lower()
    if ext in (".txt", ".md"):
        with open(path, encoding="utf-8", errors="ignore") as f:
            return _normalise(f.read())
    raise ExtractionError(
        "Reading PDF, PowerPoint, Word and image files needs P4's ingestion/extract.py. "
        "For now, upload a .txt file."
    )
