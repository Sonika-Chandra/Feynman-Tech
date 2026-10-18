# Test material

Sample study files about photosynthesis, in every format the app accepts. Regenerate them with
`python test-material/make_samples.py` (needs `pip install -r requirements-dev.txt`).

| File | Tests |
|---|---|
| `photosynthesis.pdf` | Font-size headings, a repeating header and page numbers that must be removed |
| `photosynthesis.pptx` | One topic per slide, speaker notes |
| `photosynthesis.docx` | Heading styles and a table |
| `photosynthesis.md` | Markdown headings |
| `flowchart.png` | Image to numbered steps (uses Gemini, 1 request) |
| `scanned.pdf` | PDF with no text layer: falls back to Gemini scanning (1 request) |

## The planted error

In the section **Where it happens**, the notes say:

> Chlorophyll absorbs mostly green light, which is why plants look green.

This is wrong. Chlorophyll absorbs mostly red and blue light and **reflects** green light, which is why plants look green.
Vocalis no longer fact-checks the notes. This sentence is a planted error; see how the AI marks an answer that follows it.
