import re
from collections import Counter


def strip_line_spaces(text):
    return re.sub(r"[ \t]+\n", "\n", text)


def fix_hyphens(text):
    return re.sub(r"(\w)-\n(\w)", r"\1\2", text)


def fix_broken_lines(text):
    return re.sub(r"\n(?=[a-z])", " ", text)


def remove_page_numbers(text):
    pattern = r"^\s*(?:page\s*)?\d+(?:\s*of\s*\d+)?\s*$"
    return re.sub(pattern, "", text, flags=re.MULTILINE | re.IGNORECASE)


def clean_blank_lines(text):
    return re.sub(r"\n{2,}", "\n", text).strip()


def remove_repeated_lines(pages):
    if len(pages) < 3:
        return pages
    counts = Counter()
    for page in pages:
        for line in set(l.strip() for l in page.splitlines() if l.strip()):
            counts[line] += 1
    repeated = {line for line, c in counts.items() if c > len(pages) / 2}
    cleaned = []
    for page in pages:
        keep = [l for l in page.splitlines() if l.strip() not in repeated]
        cleaned.append("\n".join(keep))
    return cleaned


def clean_pdf_pages(pages):
    pages = remove_repeated_lines(pages)
    cleaned = []
    for page in pages:
        page = strip_line_spaces(page)
        page = remove_page_numbers(page)
        page = fix_hyphens(page)
        page = fix_broken_lines(page)
        page = clean_blank_lines(page)
        cleaned.append(page)
    return cleaned


if __name__ == "__main__":
    from extract_pdf import extract_pdf_raw

    pages = extract_pdf_raw("master.pdf")
    for number, text in enumerate(clean_pdf_pages(pages), start=1):
        print("PAGE", number)
        print(text)
        print("-" * 40)

