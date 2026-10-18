"""PDF -> sections. Headings are found from font size and boldness, so real structure survives."""
import re
from collections import Counter

from . import topics
from .errors import ExtractionError


def _collect(doc):
    lines = []
    for pno, page in enumerate(doc):
        for block in page.get_text("dict").get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                spans = [s for s in line.get("spans", []) if s.get("text", "").strip()]
                if not spans:
                    continue
                text = "".join(s["text"] for s in spans).strip()
                size = max(s["size"] for s in spans)
                bold = all((s.get("flags", 0) & 16) or "bold" in s.get("font", "").lower() for s in spans)
                lines.append({"page": pno, "text": text, "size": size, "bold": bool(bold)})
    return lines


def _drop_repeats(lines, pages):
    """Removes page numbers and headers or footers that repeat on most pages."""
    def key(t):
        return re.sub(r"\d+", "#", t.strip().lower())

    seen = {}
    for l in lines:
        seen.setdefault(key(l["text"]), set()).add(l["page"])
    out = []
    for l in lines:
        t = l["text"].strip()
        if re.fullmatch(r"(page\s*)?\d{1,4}(\s*(of|/)\s*\d{1,4})?", t.lower()):
            continue
        if pages >= 3 and len(t) < 90 and len(seen[key(t)]) >= max(3, pages * 0.5):
            continue
        out.append(l)
    return out


def _join_body(texts):
    out = ""
    for t in texts:
        if not out:
            out = t
        elif out.endswith("-") and t[:1].islower():
            out = out[:-1] + t
        elif re.match(r"^([•●▪\-–*]|\d+[.)])\s", t) or (out[-1] in ".!?:" and t[:1].isupper()):
            out += "\n" + t
        else:
            out += " " + t
    return out


def _sections_by_font(lines):
    if not lines:
        return []
    weight = Counter()
    for l in lines:
        weight[round(l["size"] * 2) / 2] += len(l["text"])
    body = weight.most_common(1)[0][0]

    def is_head(l):
        t = l["text"]
        if len(t) > 100 or re.fullmatch(r"[\d\W]+", t):
            return False
        if l["size"] >= body * 1.15:
            return True
        return l["bold"] and l["size"] >= body * 0.95 and len(t) <= 70 and t[-1] not in ".,;"

    secs, title, texts, last_head_size = [], None, [], None

    def flush():
        if texts or title:
            secs.append({"title": title or "Introduction", "text": _join_body(texts)})

    i = 0
    while i < len(lines):
        l = lines[i]
        if is_head(l):
            flush()
            texts = []
            title, last_head_size = l["text"], l["size"]
            while i + 1 < len(lines) and is_head(lines[i + 1]) and abs(lines[i + 1]["size"] - last_head_size) < 0.6:
                i += 1
                title += " " + lines[i]["text"]
        else:
            texts.append(l["text"])
        i += 1
    flush()
    return secs


def read(path):
    try:
        import pymupdf as fitz
    except ImportError:          # older PyMuPDF versions
        import fitz
    try:
        doc = fitz.open(path)
    except Exception:
        raise ExtractionError("This PDF could not be opened. It may be damaged.")
    if doc.needs_pass:
        raise ExtractionError("This PDF is password protected. Remove the password and upload it again.")

    lines = _collect(doc)
    if sum(len(l["text"]) for l in lines) < 30:          # scanned PDF: no text layer
        from . import image_reader
        return topics.split_sections(image_reader.ocr_pdf(path))

    lines = _drop_repeats(lines, doc.page_count)
    secs = topics.finalize(topics.merge_small(_sections_by_font(lines)))
    if len(secs) >= 2:
        return secs
    return topics.split_sections(_join_body_pages(lines))


def _join_body_pages(lines):
    pages = {}
    for l in lines:
        pages.setdefault(l["page"], []).append(l["text"])
    return "\n\n".join(_join_body(t) for _, t in sorted(pages.items()))
