from pptx import Presentation


def extract_pptx(path):
    prs = Presentation(path)
    sections = []

    for slide in prs.slides:
        title_shape = slide.shapes.title
        title = title_shape.text.strip() if title_shape is not None else "Untitled"
        lines = []

        for shape in slide.shapes:
            if title_shape is not None and shape.shape_id == title_shape.shape_id:
                continue
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    text = "".join(run.text for run in para.runs).strip()
                    if text:
                        lines.append(text)
            if shape.has_table:
                for row in shape.table.rows:
                    cells = [cell.text.strip() for cell in row.cells]
                    lines.append(" | ".join(cells))

        sections.append({"title": title, "text": "\n".join(lines)})
    return sections


if __name__ == "__main__":
    result = extract_pptx("master.pptx")
    for item in result:
        print("TITLE:", item["title"])
        print("TEXT:", item["text"])
        print("-" * 40)