import os
import json
import glob
import difflib
import re
from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

MODEL = "gemini-3.5-flash"

PROMPT = (
    "Transcribe this audio exactly as spoken, word for word. "
    "Do not fix mistakes or add words. Return only the transcript."
)

REFERENCE = (
    "Python is a popular programming language. It is easy to read and "
    "easy to learn, so many beginners start with it. Python was created "
    "by James Gosling. It was first released in 2015. Frameworks like "
    "Django and Flask help build websites. Libraries like Pandas and "
    "NumPy help study data."
)


def words(text):
    return re.findall(r"[a-z0-9]+", text.lower())


def match_score(a, b):
    return round(difflib.SequenceMatcher(None, words(a), words(b)).ratio() * 100, 1)


def find_audio(name):
    for path in os.listdir("."):
        low = path.lower()
        if low.startswith(name) and low.endswith(
            (".mp3", ".wav", ".m4a", ".mp4", ".aac", ".flac", ".ogg")
        ):
            return path
    return None
    


def transcribe(path):
    uploaded = client.files.upload(file=path,config={"mime_type":"audio/mp4"})
    response = client.models.generate_content(
        model=MODEL, contents=[PROMPT, uploaded]
    )
    return response.text.strip()


if __name__ == "__main__":
    results = {}
    for name in ["clean", "noisy", "accent"]:
        path = find_audio(name)
        if not path:
            print(name, "- file not found")
            continue
        try:
            text = transcribe(path)
            results[name] = {"file": path, "transcript": text,
                             "match_percent": match_score(REFERENCE, text)}
            print(name.upper(), "(" + path + ")")
            print(text)
            print("Match with original:", results[name]["match_percent"], "%")
        except Exception as error:
            print(name, "- ERROR:", error)
        print("-" * 40)

    with open("transcripts.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print("Saved transcripts.json")