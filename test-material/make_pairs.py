"""
Builds 8 test files in test-material/pairs/: for each format (PDF, Word, PowerPoint, flowchart image) one CORRECT file and one
file with DELIBERATE ERRORS (listed in pairs/ANSWER_KEY.md). Run:  python test-material/make_pairs.py   (needs requirements-dev.txt)
"""
import os
from docx import Document
from pptx import Presentation
from pptx.util import Pt
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pairs")
os.makedirs(OUT, exist_ok=True)

# ------------------------------------------------------------------ content
PHOTO = {
    "title": "Photosynthesis",
    "ok": [
        ("Overview", "Photosynthesis is the process by which plants, algae and some bacteria turn light energy into chemical energy. The overall result is glucose and oxygen, made from carbon dioxide and water using light."),
        ("Where it happens", "In plants, photosynthesis takes place in chloroplasts, found mainly in leaf cells. Chloroplasts contain chlorophyll, the green pigment that captures light. Chlorophyll absorbs mostly red and blue light and reflects green light, which is why leaves look green."),
        ("Light-dependent reactions", "The first stage happens in the thylakoid membranes. Light energy is used to split water molecules. This releases oxygen as a by-product and produces two energy carriers, ATP and NADPH."),
        ("The Calvin cycle", "The second stage happens in the stroma and does not need light directly. It uses the ATP and NADPH from the first stage to turn carbon dioxide into glucose. The cycle repeats to build each sugar molecule."),
        ("What affects the rate", "Light intensity, carbon dioxide concentration and temperature change how fast photosynthesis runs. Very high temperatures slow it down because enzymes stop working properly."),
    ],
    "bad": [
        ("Overview", "Photosynthesis is the process by which plants, algae and some bacteria turn light energy into chemical energy. The overall result is glucose and oxygen, made from carbon dioxide and water using light."),
        ("Where it happens", "In plants, photosynthesis takes place in the mitochondria, found mainly in leaf cells. Mitochondria contain chlorophyll, the green pigment that captures light. Chlorophyll absorbs mostly green light, which is why leaves look green."),
        ("Light-dependent reactions", "The first stage happens in the stroma. Light energy is used to split carbon dioxide molecules. This releases oxygen as a by-product and produces two energy carriers, ATP and NADPH."),
        ("The Calvin cycle", "The second stage happens in the thylakoid membranes and needs light directly. It uses the ATP and NADPH from the first stage to turn carbon dioxide into glucose. The cycle repeats to build each sugar molecule."),
        ("What affects the rate", "Light intensity, carbon dioxide concentration and temperature change how fast photosynthesis runs. The higher the temperature, the faster it always runs, with no limit."),
    ],
}
NEWTON = {
    "title": "Newton's Laws of Motion",
    "ok": [
        ("First law: inertia", "An object stays at rest, or keeps moving in a straight line at constant speed, unless an unbalanced force acts on it. A heavier object has more inertia."),
        ("Second law: F = ma", "The net force on an object equals its mass times its acceleration, F = m x a. Example: a 10 kg trolley accelerating at 3 m/s2 needs a net force of 10 x 3 = 30 N. Force is measured in newtons (N)."),
        ("Weight", "Weight is the force of gravity on a mass, W = m x g. With g = 9.8 m/s2, a 5 kg bag weighs 5 x 9.8 = 49 N. Mass is measured in kilograms, weight in newtons."),
        ("Momentum", "Momentum is mass times velocity, p = m x v. A 2 kg ball moving at 4 m/s has momentum 2 x 4 = 8 kg m/s."),
        ("Third law: action and reaction", "When object A pushes on object B, B pushes back on A with an equal force in the opposite direction. The two forces act on different objects, so they do not cancel each other."),
    ],
    "bad": [
        ("First law: inertia", "An object stays at rest, or keeps moving in a straight line at constant speed, unless an unbalanced force acts on it. A lighter object has more inertia."),
        ("Second law: F = ma", "The net force on an object equals its mass divided by its acceleration, F = m / a. Example: a 10 kg trolley accelerating at 3 m/s2 needs a net force of 10 + 3 = 13 N. Force is measured in newtons (N)."),
        ("Weight", "Weight is the force of gravity on a mass, W = m x g. With g = 9.8 m/s2, a 5 kg bag weighs 5 x 9.8 = 49 kg. Mass and weight are the same thing and are both measured in kilograms."),
        ("Momentum", "Momentum is mass times velocity, p = m x v. A 2 kg ball moving at 4 m/s has momentum 2 x 4 = 6 kg m/s."),
        ("Third law: action and reaction", "When object A pushes on object B, B pushes back on A with an equal force in the opposite direction. The two forces act on the same object, so they always cancel each other."),
    ],
}
WATER = {
    "title": "The Water Cycle",
    "ok": [
        ("Evaporation", ["The Sun heats water in oceans, lakes and rivers.", "Liquid water turns into water vapour, a gas.", "Plants also release vapour (transpiration)."]),
        ("Condensation", ["Rising water vapour cools in the cold upper air.", "It turns back into tiny liquid droplets.", "The droplets gather to form clouds."]),
        ("Precipitation", ["Droplets grow heavy and fall as rain, snow, sleet or hail.", "The form depends on the air temperature."]),
        ("Collection", ["Water runs off into rivers and seeps into the ground.", "It collects in oceans, lakes and underground stores.", "About 97% of Earth's water is salty ocean water, so only about 3% is fresh water."]),
    ],
    "bad": [
        ("Evaporation", ["The Sun cools water in oceans, lakes and rivers.", "Liquid water turns into water vapour, a gas.", "Plants also release vapour (transpiration)."]),
        ("Condensation", ["Rising water vapour cools in the cold upper air.", "It turns into solid ice cubes that fall at once.", "The droplets gather to form clouds."]),
        ("Precipitation", ["Droplets grow heavy and fall only as rain.", "Snow, sleet and hail are not part of the water cycle."]),
        ("Collection", ["Water runs off into rivers and seeps into the ground.", "It collects in oceans, lakes and underground stores.", "About 97% of Earth's water is fresh water, and only about 3% is salty ocean water."]),
    ],
}

# ------------------------------------------------------------------ builders
def make_pdf(path, data, sections):
    st = getSampleStyleSheet()
    doc = SimpleDocTemplate(path, pagesize=A4, title=data["title"], leftMargin=60, rightMargin=60, topMargin=60)
    flow = [Paragraph(data["title"], st["Title"]), Spacer(1, 10)]
    for head, body in sections:
        flow += [Paragraph(head, st["Heading2"]), Paragraph(body, st["BodyText"]), Spacer(1, 8)]
    doc.build(flow)


def make_docx(path, data, sections):
    d = Document()
    d.add_heading(data["title"], 0)
    for head, body in sections:
        d.add_heading(head, 1)
        d.add_paragraph(body)
    d.save(path)


def make_pptx(path, data, slides):
    p = Presentation()
    t = p.slides.add_slide(p.slide_layouts[0])
    t.shapes.title.text = data["title"]
    t.placeholders[1].text = "Revision slides"
    for head, bullets in slides:
        s = p.slides.add_slide(p.slide_layouts[1])
        s.shapes.title.text = head
        tf = s.placeholders[1].text_frame
        tf.text = bullets[0]
        for b in bullets[1:]:
            tf.add_paragraph().text = b
        for para in tf.paragraphs:
            for r in para.runs:
                r.font.size = Pt(24)
    p.save(path)


def font(size, bold=False):
    for f in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
              "arialbd.ttf" if bold else "arial.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            pass
    return ImageFont.load_default()


def flowchart(path, boxes, arrows_reversed=False):
    """boxes: [(title, detail, fill)] drawn top to bottom with arrows between them."""
    W, bw, bh, gap = 900, 640, 120, 60
    H = 90 + len(boxes) * (bh + gap)
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    d.text((W // 2, 40), "Photosynthesis: process flowchart", font=font(30, True), fill="#1b1214", anchor="mm")
    x0 = (W - bw) // 2
    for i, (title, detail, fill) in enumerate(boxes):
        y = 90 + i * (bh + gap)
        d.rounded_rectangle([x0, y, x0 + bw, y + bh], 18, fill=fill, outline="#1b1214", width=4)
        d.text((W // 2, y + 38), title, font=font(26, True), fill="#1b1214", anchor="mm")
        d.text((W // 2, y + 82), detail, font=font(21), fill="#1b1214", anchor="mm")
        if i < len(boxes) - 1:
            top, bot = y + bh + 4, y + bh + gap - 4
            a, b = (bot, top) if arrows_reversed and i == len(boxes) - 2 else (top, bot)
            d.line([W // 2, a, W // 2, b], fill="#8f2a3f", width=6)
            s = 1 if b > a else -1
            d.polygon([(W // 2 - 14, b - 16 * s), (W // 2 + 14, b - 16 * s), (W // 2, b)], fill="#8f2a3f")
    img.save(path)


# ------------------------------------------------------------------ write files
make_pdf(os.path.join(OUT, "1_photosynthesis_CORRECT.pdf"), PHOTO, PHOTO["ok"])
make_pdf(os.path.join(OUT, "2_photosynthesis_WITH_ERRORS.pdf"), PHOTO, PHOTO["bad"])
make_docx(os.path.join(OUT, "3_newtons_laws_CORRECT.docx"), NEWTON, NEWTON["ok"])
make_docx(os.path.join(OUT, "4_newtons_laws_WITH_ERRORS.docx"), NEWTON, NEWTON["bad"])
make_pptx(os.path.join(OUT, "5_water_cycle_CORRECT.pptx"), WATER, WATER["ok"])
make_pptx(os.path.join(OUT, "6_water_cycle_WITH_ERRORS.pptx"), WATER, WATER["bad"])
flowchart(os.path.join(OUT, "7_photosynthesis_flowchart_CORRECT.png"), [
    ("Inputs", "Sunlight + water (H2O) + carbon dioxide (CO2)", "#e8f1d8"),
    ("Light-dependent reactions", "In the thylakoid membranes. Water is split, O2 is released", "#cfe8f5"),
    ("ATP and NADPH made", "Energy carriers passed to the next stage", "#f6e3c8"),
    ("Calvin cycle", "In the stroma. Uses ATP, NADPH and CO2", "#e7c9d6"),
    ("Glucose (sugar) made", "Stored as food for the plant", "#e8f1d8"),
])
flowchart(os.path.join(OUT, "8_photosynthesis_flowchart_WITH_ERRORS.png"), [
    ("Inputs", "Sunlight + oxygen (O2) + glucose", "#e8f1d8"),
    ("Light-dependent reactions", "In the stroma. Carbon dioxide is split, glucose is released", "#cfe8f5"),
    ("ATP and NADPH made", "Energy carriers passed to the next stage", "#f6e3c8"),
    ("Calvin cycle", "In the thylakoid membranes. Needs no ATP or NADPH", "#e7c9d6"),
    ("Glucose (sugar) made", "Stored as food for the plant", "#e8f1d8"),
], arrows_reversed=True)

open(os.path.join(OUT, "ANSWER_KEY.md"), "w").write("""# Answer key for the test pairs

Upload the CORRECT file: the fact-check should say "No suspected errors found" (or only trivial remarks).
Upload the WITH_ERRORS file: the fact-check should flag the errors below. Also try explaining the correct facts after uploading the wrong notes, and see whether the contradiction between your answer and the notes is caught.

## 2_photosynthesis_WITH_ERRORS.pdf (6 errors)
1. Photosynthesis happens in the **mitochondria** (correct: chloroplasts).
2. Chlorophyll is said to be in mitochondria (correct: chloroplasts).
3. Chlorophyll "absorbs mostly green light" (correct: absorbs red and blue, reflects green).
4. First stage "in the stroma" (correct: thylakoid membranes).
5. Light splits **carbon dioxide** (correct: water; the oxygen comes from water).
6. Calvin cycle "in the thylakoid membranes and needs light directly" (correct: stroma, no direct light).
7. "The higher the temperature, the faster it always runs" (correct: very high temperature slows it, enzymes stop working).

## 4_newtons_laws_WITH_ERRORS.docx (6 errors)
1. "A lighter object has more inertia" (correct: heavier).
2. F = m / a (correct: F = m x a).
3. 10 kg at 3 m/s2 "= 10 + 3 = 13 N" (correct: 30 N).
4. 5 x 9.8 = 49 **kg** and "mass and weight are the same" (correct: 49 N; different quantities).
5. Momentum 2 x 4 = **6** (correct: 8 kg m/s).
6. Action and reaction act on the **same** object and always cancel (correct: different objects, so they do not cancel).

## 6_water_cycle_WITH_ERRORS.pptx (5 errors)
1. The Sun **cools** the water (correct: heats it).
2. Condensation forms **solid ice cubes** (correct: liquid droplets).
3. Precipitation is **only rain** (correct: rain, snow, sleet, hail).
4. "Snow, sleet and hail are not part of the water cycle" (correct: they are).
5. 97% of Earth's water is **fresh** (correct: about 97% is salty ocean water, about 3% fresh).

## 8_photosynthesis_flowchart_WITH_ERRORS.png (7 errors)
1. Inputs list **oxygen and glucose** (correct: sunlight, water, carbon dioxide).
2. Light reactions placed in the **stroma** (correct: thylakoid membranes).
3. **CO2 is split** and glucose released (correct: water is split, O2 released).
4. Calvin cycle in the **thylakoid membranes** (correct: stroma).
5. Calvin cycle "needs no ATP or NADPH" (correct: it uses them).
6. The last arrow points **backwards** (glucose to Calvin cycle; correct: Calvin cycle to glucose).
7. The flowchart is read by Gemini vision, so also check the text is read correctly: this is the OCR test.

## Suggested checks
- Each file uploads and splits into topics (the flowchart gives one topic).
- The correct files give no fact-check warnings; the error files give the warnings above.
- Run a session on an error file but answer with the correct facts: the questions and score should show where the notes disagree.
""")
print("done")
