import fitz
from collections import Counter
from clean_text import (
    strip_line_spaces,
    remove_page_numbers,
    fix_hyphens,
    fix_broken_lines,
    clean_blank_lines,
)


def get_lines(path):
    doc = fitz.open(path)
    lines = []
    for page in doc:
        for block in page.get_text("dict")["blocks"]:
            if block["type"] != 0:
                continue
            for line in block["lines"]:
                text = "".join(s["text"] for s in line["spans"]).strip()
                if not text:
                    continue
                size = round(max(s["size"] for s in line["spans"]), 1)
                lines.append((text, size))
    return lines


def clean_section_text(text):
    text = strip_line_spaces(text)
    text = remove_page_numbers(text)
    text = fix_hyphens(text)
    text = fix_broken_lines(text)
    return clean_blank_lines(text)


def extract_pdf(path):
    lines = get_lines(path)
    if not lines:
        return []

    sizes = Counter()
    for text, size in lines:
        sizes[size] += len(text)
    body_size = sizes.most_common(1)[0][0]

    sections = []
    current = None
    for text, size in lines:
        if size >= body_size + 1:
            if current:
                sections.append(current)
            current = {"title": text, "text": ""}
        else:
            if current is None:
                current = {"title": "Untitled", "text": ""}
            current["text"] += text + "\n"
    if current:
        sections.append(current)

    for item in sections:
        item["text"] = clean_section_text(item["text"])
    return sections


if __name__ == "__main__":
    for item in extract_pdf("master.pdf"):
        print("TITLE:", item["title"])
        print("TEXT:", item["text"])
        print("-" * 40)