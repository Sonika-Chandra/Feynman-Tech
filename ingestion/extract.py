import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from docx_reader import extract_docx
from pptx_reader import extract_pptx
from pdf_reader import extract_pdf
from topics import tag_topics

AUDIO_TYPES = (".mp3", ".wav", ".m4a", ".mp4", ".aac", ".flac", ".ogg")
IMAGE_TYPES = (".png", ".jpg", ".jpeg")


def extract(path):
    """One entry point. Returns a list of {"title", "text", "topic"}."""
    ending = os.path.splitext(path)[1].lower()

    if ending == ".docx":
        return tag_topics(extract_docx(path))
    if ending == ".pptx":
        return tag_topics(extract_pptx(path))
    if ending == ".pdf":
        return tag_topics(extract_pdf(path))

    if ending in AUDIO_TYPES:
        from audio import transcribe
        text = transcribe(path)
        return [{"title": "Audio transcript", "text": text, "topic": "transcript"}]

    if ending in IMAGE_TYPES:
        from image_reader import read_flowchart
        steps = read_flowchart(path)
        text = "\n".join(f"{n}. {s}" for n, s in enumerate(steps, start=1))
        return tag_topics([{"title": "Flowchart steps", "text": text}])

    raise ValueError("Unsupported file type: " + ending)


if __name__ == "__main__":
    import json

    if len(sys.argv) < 2:
        print("Usage: python ingestion/extract.py <file>")
        sys.exit(1)
    print(json.dumps(extract(sys.argv[1]), indent=2, ensure_ascii=False))