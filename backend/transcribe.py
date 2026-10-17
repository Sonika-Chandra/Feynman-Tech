"""Audio answer -> text, using Gemini. P4 can replace this with their own version."""
from google.genai import types

from ai import ai_module

SYSTEM = "You are a precise transcription tool. Output only the words spoken, with no commentary."


def transcribe(data: bytes, mime_type: str) -> str:
    part = types.Part.from_bytes(data=data, mime_type=mime_type or "audio/webm")
    resp = ai_module._generate([part, "Transcribe this audio."], SYSTEM)
    return (resp.text or "").strip()
