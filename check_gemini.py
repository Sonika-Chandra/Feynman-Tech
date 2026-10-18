"""
Tests your Gemini key against each model, one tiny request each, and shows Google's real answer.
Run from the repo root:    python check_gemini.py
It uses the key and models from your .env (GEMINI_API_KEY, GEMINI_MODEL, GEMINI_FALLBACK_MODELS).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from ai import ai_module as ai
except Exception as e:  # noqa: BLE001
    sys.exit(f"Could not load the AI module: {e}\nRun: pip install -r requirements.txt")

st = ai.status()
print("Key in use ends with:", st["key_ending"] or "(NO KEY FOUND: check GEMINI_API_KEY in .env)")
if not st["key_ending"]:
    sys.exit(1)
print("Models to test:", ", ".join(st["models"]), "\n")

any_ok = False
for model in st["models"]:
    try:
        r = ai._get_client().models.generate_content(model=model, contents="Reply with the single word OK.")
        print(f"WORKS    {model}   -> {(r.text or '').strip()[:20]}")
        any_ok = True
    except Exception as e:  # noqa: BLE001
        text = str(e).replace("\n", " ")
        why = "no free allowance for this model on this key (limit: 0)" if "limit: 0" in text else \
              "daily free quota used up" if "PerDay" in text else \
              "model name not found" if "NOT_FOUND" in text or "not found" in text else \
              "key rejected (wrong or disabled key)" if "API key" in text or "API_KEY" in text or "403" in text[:20] else \
              "temporary rate limit: wait a minute" if "429" in text else "other error"
        print(f"FAILS    {model}   -> {why}\n         Google said: {text[:260]}")
print()
if any_ok:
    print("At least one model works. Put it first as GEMINI_MODEL=... in .env and restart the backend.")
else:
    print("No model worked with this key. If every line says 'limit: 0' or 'daily quota', the Google project behind the key")
    print("has no free allowance left (or none in your region). Use a key from a NEW AI Studio project, or enable billing.")
    print("Create a fresh key in a NEW project at aistudio.google.com, put it in .env and RESTART the backend.")
sys.exit(0 if any_ok else 1)
