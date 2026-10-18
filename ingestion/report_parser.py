"""
Reads a mistake report (the Markdown file the app produces) so it can be uploaded again.
Each past mistake becomes a topic, so the student practises exactly what they got wrong.
The report format is fixed by ai/ai_module.py (REPORT_HEADINGS).
"""
import re

from .errors import ExtractionError

_HEAD = re.compile(r"^###\s+(Concept Misunderstood|Correct Explanation|Recommended Review)\s*$", re.M)


def is_report(text):
    return (text or "").lstrip().startswith("# Mistake Report")


def parse(text):
    """Returns {"overall": int|None, "mistakes": [{"concept","correct","review"}], "suspected": str}."""
    m = re.search(r"Overall:\s*(\d+)\s*/\s*100", text)
    overall = int(m.group(1)) if m else None

    suspected = ""
    s = re.search(r"^##\s+Suspected Issues In Study Material\s*$", text, re.M)
    body = text
    if s:
        suspected = text[s.end():].strip()
        body = text[: s.start()]

    mi = re.search(r"^##\s+Mistakes\s*$", body, re.M)
    body = body[mi.end():] if mi else body

    mistakes = []
    for block in re.split(r"^---+\s*$", body, flags=re.M):
        parts = _HEAD.split(block)            # [pre, name, text, name, text, ...]
        found = {parts[i]: parts[i + 1].strip() for i in range(1, len(parts) - 1, 2)}
        if found.get("Concept Misunderstood"):
            mistakes.append({
                "concept": found.get("Concept Misunderstood", ""),
                "correct": found.get("Correct Explanation", ""),
                "review": found.get("Recommended Review", ""),
            })
    return {"overall": overall, "mistakes": mistakes, "suspected": suspected}


def to_sections(text):
    data = parse(text)
    if not data["mistakes"]:
        raise ExtractionError("This mistake report lists no mistakes to practise. Try a new session instead.")
    secs, everything = [], []
    for k, m in enumerate(data["mistakes"], 1):
        concept = " ".join(m["concept"].split())
        body = f"Mistake: {concept}\nCorrect explanation: {m['correct']}\nHow to review: {m['review']}".strip()
        secs.append({"title": f"Mistake {k}: {concept[:70]}", "text": body})
        everything.append(body)
    if len(secs) > 1:
        secs.insert(0, {"title": "All my mistakes", "text": "\n\n".join(everything)})
    return secs
