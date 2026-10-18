"""
Tests for Role 4. Run from the repo root:   python ingestion/test_ingestion.py
Free: images, scanned PDFs and audio use the fake AI (no Gemini requests).
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["USE_FAKE_AI"] = "1"

from ingestion import ExtractionError, extract            # noqa: E402
from ingestion import audio, report_parser, topics         # noqa: E402

SAMPLES = os.path.join(ROOT, "test-material")
failures = []


def check(name, ok, detail=""):
    print(("PASS  " if ok else "FAIL  ") + name + (f"\n        {detail}" if (detail and not ok) else ""))
    if not ok:
        failures.append(name)


def titles(sections):
    return [s["title"] for s in sections]


def joined(sections):
    return " ".join(s["text"] for s in sections)


# make sure the samples exist
if not os.path.exists(os.path.join(SAMPLES, "photosynthesis.pdf")):
    import subprocess
    subprocess.run([sys.executable, os.path.join(SAMPLES, "make_samples.py")], check=True)

# ---------------------------------------------------------------- PDF
s = extract(os.path.join(SAMPLES, "photosynthesis.pdf"))
check("pdf: finds the real headings", {"Overview", "Where it happens", "Light-dependent reactions", "The Calvin cycle"} <= set(titles(s)), str(titles(s)))
check("pdf: body text kept", "thylakoid membranes" in joined(s))
check("pdf: repeating header and page numbers removed", "Biology notes" not in joined(s) and "Page 1" not in joined(s))
check("pdf: sentences are joined, not one word per line", "\n" not in next(x for x in s if x["title"] == "Overview")["text"].strip()[:60])

# ---------------------------------------------------------------- PowerPoint
s = extract(os.path.join(SAMPLES, "photosynthesis.pptx"))
check("pptx: one topic per slide", len(s) == 6, str(titles(s)))
check("pptx: slide titles used", "The Calvin cycle" in titles(s))
check("pptx: speaker notes included", "Say this in your own words" in joined(s))

# ---------------------------------------------------------------- Word
s = extract(os.path.join(SAMPLES, "photosynthesis.docx"))
check("docx: heading styles become topics", {"Overview", "Where it happens", "The Calvin cycle"} <= set(titles(s)), str(titles(s)))
check("docx: table text included", "ATP, NADPH and oxygen" in joined(s))

# ---------------------------------------------------------------- Markdown and text
s = extract(os.path.join(SAMPLES, "photosynthesis.md"))
check("md: markdown headings become topics", "Light-dependent reactions" in titles(s), str(titles(s)))

tmp = tempfile.mkdtemp()
p = os.path.join(tmp, "plain.txt")
open(p, "w").write("Plants make food from light. " * 10)
s = extract(p)
check("txt: short text without headings -> one topic", titles(s) == ["Whole document"], str(titles(s)))

p = os.path.join(tmp, "long.txt")
open(p, "w").write("\n\n".join(f"Paragraph {i}. " + "Plants use light to make sugar. " * 12 for i in range(30)))
s = extract(p)
check("txt: long text without headings -> Part 1, Part 2, ...", len(s) >= 3 and s[0]["title"].startswith("Part 1"), str(titles(s)[:3]))

p = os.path.join(tmp, "dup.md")
open(p, "w").write("# Notes\n\n## Topic\n\n" + "First body text here. " * 5 + "\n\n## Topic\n\n" + "Second body text here. " * 5)
check("duplicate titles made unique", titles(extract(p))[-2:] == ["Topic", "Topic (2)"], str(titles(extract(p))))

# ---------------------------------------------------------------- Images and scanned PDFs (fake AI)
s = extract(os.path.join(SAMPLES, "flowchart.png"))
check("image: becomes numbered steps", s[0]["title"].startswith("Image:") and "1." in s[0]["text"])
s = extract(os.path.join(SAMPLES, "scanned.pdf"))
check("scanned pdf: falls back to AI scanning", "placeholder text from a scanned PDF" in joined(s), str(s))

# ---------------------------------------------------------------- Mistake report
report = (
    "# Mistake Report\n\n## Score Summary\n- Overall: 62/100\n- Accuracy: 6/10\n\n## Mistakes\n\n"
    "### Concept Misunderstood\nYou said plants breathe in oxygen.\n\n### Correct Explanation\nPlants take in carbon dioxide.\n\n"
    "### Recommended Review\nRedraw the gas exchange diagram.\n\n---\n\n"
    "### Concept Misunderstood\nChlorophyll absorbs green light.\n\n### Correct Explanation\nIt reflects green light.\n\n"
    "### Recommended Review\nLook at the absorption spectrum.\n\n## Suspected Issues In Study Material\n- Where: study material\n"
)
parsed = report_parser.parse(report)
check("report: parsed overall and 2 mistakes", parsed["overall"] == 62 and len(parsed["mistakes"]) == 2, str(parsed))
check("report: suspected issues captured", "study material" in parsed["suspected"])
p = os.path.join(tmp, "report.md")
open(p, "w").write(report)
s = extract(p)
check("report: each mistake becomes a topic", len(s) == 3 and s[0]["title"] == "All my mistakes" and s[1]["title"].startswith("Mistake 1"), str(titles(s)))
check("report: correct explanation kept in the text", "Plants take in carbon dioxide" in s[1]["text"])

# the report the AI module really produces can be read back
sys.path.insert(0, os.path.join(ROOT, "backend"))
import fake_ai                                                          # noqa: E402
real_shape = fake_ai.full_package("x", [])["report_markdown"]
check("report: format produced by the app can be re-uploaded", len(report_parser.parse(real_shape)["mistakes"]) == 1)

# ---------------------------------------------------------------- Errors
def raises(fn, text):
    try:
        fn()
    except ExtractionError as e:
        return text.lower() in str(e).lower()
    except Exception:
        return False
    return False


p = os.path.join(tmp, "old.doc"); open(p, "wb").write(b"x")
check("error: .doc explained", raises(lambda: extract(p), "save it as .docx"))
p = os.path.join(tmp, "x.xyz"); open(p, "wb").write(b"x")
check("error: unknown type explained", raises(lambda: extract(p), "not supported"))
p = os.path.join(tmp, "empty.txt"); open(p, "w").write("   ")
check("error: empty file explained", raises(lambda: extract(p), "enough readable text"))
p = os.path.join(tmp, "bad.pdf"); open(p, "wb").write(b"not really a pdf")
check("error: damaged pdf gives a friendly message", raises(lambda: extract(p), "pdf"))
p = os.path.join(tmp, "bad.docx"); open(p, "wb").write(b"not really a docx")
check("error: damaged docx gives a friendly message", raises(lambda: extract(p), "word file"))
p = os.path.join(tmp, "nomistakes.md"); open(p, "w").write("# Mistake Report\n\n## Mistakes\n\nNo significant mistakes found.\n")
check("error: report with no mistakes explained", raises(lambda: extract(p), "no mistakes"))

# ---------------------------------------------------------------- Audio helpers
check("audio: mime types normalised", audio.normalise_mime("audio/x-wav") == "audio/wav" and audio.normalise_mime("audio/ogg;codecs=opus") == "audio/ogg" and audio.normalise_mime("audio/mpeg") == "audio/mp3")
check("audio: fake transcript works", "fake transcript" in audio.transcribe(b"RIFFxxxx", "audio/wav"))
check("audio: empty recording rejected", raises(lambda: audio.transcribe(b"", "audio/wav"), "empty"))

from ingestion import topics as _T
_g = _T.retitle_generic([{"title": "Part 1: the cell is the basic", "text": "The cell is the basic unit of life. It has a nucleus."},
                         {"title": "Part 2: mitochondria make energy", "text": "Mitochondria produce ATP through respiration. They have two membranes."},
                         {"title": "Newton's Laws", "text": "Force equals mass times acceleration."}])
check("generic 'Part N' titles get readable headings", _g[0]["title"].startswith("Cell") and _g[1]["title"].startswith("Mitochondria"), str([x["title"] for x in _g]))
check("real headings are kept", _g[2]["title"] == "Newton's Laws")

print("\n" + ("ALL INGESTION TESTS PASSED" if not failures else f"{len(failures)} FAILED: {failures}"))
sys.exit(1 if failures else 0)
