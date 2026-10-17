from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph


def is_heading(paragraph):
    name = paragraph.style.name.lower()
    return name.startswith("heading") or name == "title"


def extract_docx(path):
    doc = Document(path)
    sections = []
    current = None

    for child in doc.element.body.iterchildren():
        if child.tag.endswith("}p"):
            para = Paragraph(child, doc)
            text = para.text.strip()
            if not text:
                continue
            if is_heading(para):
                if current:
                    sections.append(current)
                current = {"title": text, "text": ""}
            else:
                if current is None:
                    current = {"title": "Untitled", "text": ""}
                current["text"] += text + "\n"

        elif child.tag.endswith("}tbl"):
            table = Table(child, doc)
            if current is None:
                current = {"title": "Untitled", "text": ""}
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells]
                current["text"] += " | ".join(cells) + "\n"

    if current:
        sections.append(current)

    for item in sections:
        item["text"] = item["text"].strip()
    return sections


if __name__ == "__main__":
    result = extract_docx("master.docx")
    for item in result:
        print("TITLE:", item["title"])
        print("TEXT:", item["text"])
        print("-" * 40)