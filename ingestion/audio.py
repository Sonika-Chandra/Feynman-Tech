"""Spoken answer (audio file) -> text, using Gemini."""
import shutil
import subprocess

from ._llm import ask, fake_mode, part
from .errors import ExtractionError

SUPPORTED = {"audio/wav", "audio/mp3", "audio/aiff", "audio/aac", "audio/ogg", "audio/flac"}
ALIASES = {
    "audio/x-wav": "audio/wav", "audio/wave": "audio/wav", "audio/vnd.wave": "audio/wav",
    "audio/mpeg": "audio/mp3", "audio/x-aiff": "audio/aiff", "audio/x-flac": "audio/flac",
}
SYSTEM = (
    "You are a precise speech-to-text tool for a student explaining a topic out loud (often with an Indian English accent). "
    "Write exactly the words that were spoken, in order, with normal punctuation and capital letters. "
    "Do not summarise, correct the grammar, translate or add commentary. Drop only filler sounds like 'um' and 'uh'. "
    "If a word is unclear, use the closest word that fits the topic. "
    "Output only the transcript. If there is no speech, output nothing."
)
MAX_BYTES = 18 * 1024 * 1024


def normalise_mime(mime_type):
    m = (mime_type or "").split(";")[0].strip().lower()
    return ALIASES.get(m, m)


def _to_wav(data):
    """Converts any audio to 16 kHz mono WAV with ffmpeg, if ffmpeg is installed. Returns None otherwise."""
    exe = shutil.which("ffmpeg")
    if not exe:
        return None
    try:
        r = subprocess.run([exe, "-v", "error", "-i", "pipe:0", "-ac", "1", "-ar", "16000", "-f", "wav", "pipe:1"],
                           input=data, capture_output=True, timeout=60)
        return r.stdout if r.returncode == 0 and r.stdout else None
    except Exception:  # noqa: BLE001
        return None


def transcribe(data, mime_type, context=None):
    """`context` is an optional piece of the study material; it helps Gemini spell technical terms correctly."""
    if not data:
        raise ExtractionError("The audio recording was empty.")
    if len(data) > MAX_BYTES:
        raise ExtractionError("The recording is too long. Keep each answer under a few minutes.")
    if fake_mode():
        return "(fake transcript of the spoken answer)"

    mime = normalise_mime(mime_type)
    if mime not in SUPPORTED:
        wav = _to_wav(data)
        if wav:
            data, mime = wav, "audio/wav"
        # otherwise try the original format anyway; Gemini may accept it

    prompt = "Transcribe this audio."
    if context:
        prompt += ("\n\nThe speaker is explaining the following topic. Use it only to spell technical terms and names correctly; "
                   "do not add words that were not spoken:\n" + context[:1500])
    text = ask([part(data, mime or "audio/wav"), prompt], SYSTEM, "")
    if not text:
        raise ExtractionError("No speech was heard in the recording.")
    return text
