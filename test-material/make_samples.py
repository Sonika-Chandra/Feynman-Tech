"""
Creates the sample study files in this folder (run once):   python test-material/make_samples.py
Needs the dev packages: pip install -r requirements-dev.txt
The notes are our own wording about photosynthesis. ONE sentence is deliberately wrong (see NOTES.md).
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))

TITLE = "Photosynthesis"
SECTIONS = [
    ("Overview",
     "Photosynthesis is the process by which plants, algae and some bacteria turn light energy into chemical energy. "
     "The overall result is glucose and oxygen, made from carbon dioxide and water using light."),
    ("Where it happens",
     "In plants, photosynthesis takes place in chloroplasts, which are found mainly in leaf cells. Chloroplasts contain "
     "chlorophyll, the green pigment that captures light. Chlorophyll absorbs mostly green light, which is why plants look green."),
    ("Light-dependent reactions",
     "The first stage happens in the thylakoid membranes. Chlorophyll absorbs sunlight and uses its energy to split water. "
     "This releases oxygen as a by-product and produces two energy carriers, ATP and NADPH."),
    ("The Calvin cycle",
     "The second stage happens in the stroma of the chloroplast and does not need light directly. The plant uses the ATP and "
     "NADPH from the first stage to turn carbon dioxide into glucose. The cycle repeats many times to build each sugar molecule."),
    ("What affects the rate",
     "Three main factors change how fast photosynthesis runs: light intensity, carbon dioxide concentration and temperature. "
     "If any one of them is in short supply, it limits the whole process."),
]


def make_docx():
    from docx import Document
    d = Document()
    d.add_heading(TITLE, level=0)
    for title, body in SECTIONS:
        d.add_heading(title, level=1)
        d.add_paragraph(body)
    t = d.add_table(rows=3, cols=2)
    for r, (a, b) in enumerate([("Stage", "Main product"), ("Light-dependent reactions", "ATP, NADPH and oxygen"),
                                ("Calvin cycle", "Glucose")]):
        t.cell(r, 0).text, t.cell(r, 1).text = a, b
    d.save(os.path.join(HERE, "photosynthesis.docx"))


def make_pptx():
    from pptx import Presentation
    prs = Presentation()
    s = prs.slides.add_slide(prs.slide_layouts[0])
    s.shapes.title.text = TITLE
    s.placeholders[1].text = "A short introduction"
    for title, body in SECTIONS:
        s = prs.slides.add_slide(prs.slide_layouts[1])
        s.shapes.title.text = title
        s.placeholders[1].text = body
        s.notes_slide.notes_text_frame.text = "Say this in your own words."
    prs.save(os.path.join(HERE, "photosynthesis.pptx"))


def make_pdf():
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import simpleSplit
    c = canvas.Canvas(os.path.join(HERE, "photosynthesis.pdf"), pagesize=A4)
    w, h = A4
    pages = [[("title", TITLE)] + [x for s in SECTIONS[:2] for x in (("h", s[0]), ("p", s[1]))],
             [x for s in SECTIONS[2:4] for x in (("h", s[0]), ("p", s[1]))],
             [x for s in SECTIONS[4:] for x in (("h", s[0]), ("p", s[1]))]]
    for n, items in enumerate(pages, 1):
        y = h - 70
        c.setFont("Helvetica", 9)
        c.drawString(60, h - 35, "Biology notes: unit 3")                 # repeating header
        for kind, text in items:
            if kind == "title":
                c.setFont("Helvetica-Bold", 24); c.drawString(60, y, text); y -= 40
            elif kind == "h":
                y -= 10; c.setFont("Helvetica-Bold", 16); c.drawString(60, y, text); y -= 24
            else:
                c.setFont("Helvetica", 11)
                for line in simpleSplit(text, "Helvetica", 11, w - 120):
                    c.drawString(60, y, line); y -= 15
                y -= 8
        c.setFont("Helvetica", 9)
        c.drawString(w / 2, 30, f"Page {n}")                              # page number
        c.showPage()
    c.save()


def make_png():
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (640, 520), "white")
    d = ImageDraw.Draw(img)

    def box(x, y, text, w=300, h=60):
        d.rectangle([x, y, x + w, y + h], outline="black", width=2)
        d.text((x + 12, y + h // 2 - 6), text, fill="black")

    box(170, 20, "Sunlight hits the leaf")
    box(170, 120, "Chlorophyll absorbs light")
    box(170, 220, "Water is split: oxygen released")
    box(170, 320, "ATP and NADPH made")
    box(170, 420, "Calvin cycle makes glucose")
    for y in (80, 180, 280, 380):
        d.line([320, y, 320, y + 40], fill="black", width=2)
        d.polygon([(312, y + 32), (328, y + 32), (320, y + 42)], fill="black")
    img.save(os.path.join(HERE, "flowchart.png"))


def make_scanned_pdf():
    """A PDF that contains only a picture of text (no text layer)."""
    from PIL import Image, ImageDraw
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    img = Image.new("RGB", (800, 400), "white")
    d = ImageDraw.Draw(img)
    for i, line in enumerate(["Scanned notes", "Plants make glucose using light, water and carbon dioxide."]):
        d.text((30, 30 + i * 40), line, fill="black")
    p = os.path.join(HERE, "_scan.png")
    img.save(p)
    c = canvas.Canvas(os.path.join(HERE, "scanned.pdf"), pagesize=A4)
    c.drawImage(p, 40, 400, width=500, height=250)
    c.save()
    os.remove(p)


def make_markdown():
    lines = [f"# {TITLE}", ""]
    for title, body in SECTIONS:
        lines += [f"## {title}", "", body, ""]
    open(os.path.join(HERE, "photosynthesis.md"), "w", encoding="utf-8").write("\n".join(lines))


if __name__ == "__main__":
    for fn in (make_docx, make_pptx, make_pdf, make_png, make_scanned_pdf, make_markdown):
        fn()
        print("created", fn.__name__.replace("make_", ""))
