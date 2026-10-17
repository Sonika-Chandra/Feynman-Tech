import os
import json
import re
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

MODEL = "gemini-3.5-flash"

PROMPT = (
    "This image is a flowchart. List every step in order, following the "
    "arrows. Return only a JSON list of strings, like "
    '["Step one", "Step two"]. No extra text.'
)


def read_flowchart(path):
    with open(path, "rb") as f:
        image = types.Part.from_bytes(data=f.read(), mime_type="image/png")
    response = client.models.generate_content(model=MODEL, contents=[PROMPT, image])
    text = response.text.strip().replace("```json", "").replace("```", "").strip()
    return [re.sub(r"^\s*\d+\.\s*", "", s) for s in json.loads(text)]


if __name__ == "__main__":
    steps = read_flowchart("flowchart.png")
    for number, step in enumerate(steps, start=1):
        print(f"{number}. {step}")
    with open("flowchart_steps.json", "w", encoding="utf-8") as f:
        json.dump(steps, f, indent=2, ensure_ascii=False)
    print("Saved flowchart_steps.json")