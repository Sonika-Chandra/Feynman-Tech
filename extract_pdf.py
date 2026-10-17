import fitz  # this is PyMuPDF


def extract_pdf_raw(path):
    doc = fitz.open(path)
    pages = []
    for page in doc:
        pages.append(page.get_text())
    return pages


if __name__ == "__main__":
    pages = extract_pdf_raw("master.pdf")
    for number, text in enumerate(pages, start=1):
        print("PAGE", number)
        print(repr(text))
        print("-" * 40)