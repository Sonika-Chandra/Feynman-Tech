"""
The one place the ingestion code talks to Gemini (used for images, scanned PDFs and audio).
It reuses the AI module's retrying call, and returns canned text when USE_FAKE_AI=1 so nothing is spent.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def fake_mode():
    return os.getenv("USE_FAKE_AI", "0") == "1"


def part(data, mime_type):
    from google.genai import types
    return types.Part.from_bytes(data=data, mime_type=mime_type)


def ask(contents, system, fake_text):
    """Returns Gemini's text answer, or fake_text in fake mode."""
    if fake_mode():
        return fake_text
    from ai import ai_module
    resp = ai_module._generate(contents, system)
    return (resp.text or "").strip()
