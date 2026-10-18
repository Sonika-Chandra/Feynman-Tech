"""Word -> topics from Heading styles (tables are included as text)."""
from . import topics
from .errors import ExtractionError


def read(path):
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    try:
        doc = Document(path)
    except Exception:
        raise ExtractionError("This Word file could not be opened. Save it as .docx and try again.")

    secs, title, lines, flat = [], None, [], []
    n_heads = 0

    def flush():
        body = "\n".join(lines).strip()
        if body or title:
            secs.append({"title": title or "Introduction", "text": body})

    for child in doc.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            para = Paragraph(child, doc)
            text = para.text.strip()
            if not text:
                continue
            style = (para.style.name or "").lower() if para.style is not None else ""
            flat.append(text)
            if style.startswith("heading") or style == "title":
                flush()
                lines, title = [], text
                n_heads += 1
            else:
                lines.append(text)
        elif tag == "tbl":
            for row in Table(child, doc).rows:
                cells = []
                for c in row.cells:
                    t = c.text.strip()
                    if t and t not in cells:
                        cells.append(t)
                if cells:
                    line = " | ".join(cells)
                    lines.append(line)
                    flat.append(line)
    flush()

    if flat and flat[0].strip() == "Vocalis Gap Report":      # a gap report downloaded from Vocalis: practise its gaps
        gaps = [x for x in secs if x["title"].startswith("Gap ") and x["text"].strip()]
        if gaps:
            for x in gaps:
                x["title"] = x["title"].replace("Gap ", "Mistake ", 1)
            if len(gaps) > 1:
                gaps.insert(0, {"title": "All my gaps", "text": "\n\n".join(x["title"] + "\n" + x["text"] for x in gaps)})
            return topics.finalize(gaps)
    result = topics.finalize(topics.merge_small(secs)) if n_heads >= 2 else []
    if len(result) >= 2:
        return result
    return topics.split_sections("\n\n".join(flat))
