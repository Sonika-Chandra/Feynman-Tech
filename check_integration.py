"""
One command to verify Role 1 (ai/) and Role 3 (backend/) are consistent and working together.

    python check_integration.py          # free: no Gemini calls
    python check_integration.py --real   # also runs the real AI through the backend (uses about 2 requests)
"""
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.join(ROOT, "backend")
REAL = "--real" in sys.argv

# Never touch your real database while checking.
os.environ["DATABASE_PATH"] = os.path.join(tempfile.mkdtemp(), "check.db")
sys.path.insert(0, ROOT)
sys.path.insert(0, BACKEND)

failures = []


def check(name, ok, detail=""):
    print(("PASS  " if ok else "FAIL  ") + name + (f"\n        {detail}" if (detail and not ok) else ""))
    if not ok:
        failures.append(name)
    return ok


def hint(message):
    m = message.lower()
    if "api_key" in m or "api key" in m:
        return "Put GEMINI_API_KEY in the .env file in the repo root (same folder as check_integration.py)."
    if "perday" in m or "daily" in m or "429" in m or "resource_exhausted" in m or "quota" in m:
        return "Gemini quota used up. Change GEMINI_MODEL in .env, wait for the reset, or enable billing."
    if "404" in m or "not_found" in m or "not found" in m:
        return "The model name is not valid. Check GEMINI_MODEL in .env against Google AI Studio."
    return ""


# ------------------------------------------------------------------ 1. files
print("\n[1] Files")
required = [
    "ai/__init__.py", "ai/ai_module.py", "ai/prompts.py", "ai/test_ai.py", "ai/hello_gemini.py",
    "backend/app.py", "backend/database.py", "backend/material.py", "backend/transcribe.py",
    "backend/fake_ai.py", "backend/test_api.py", "docs/api.md", "requirements.txt", ".gitignore", ".env.example",
]
missing = [f for f in required if not os.path.exists(os.path.join(ROOT, f))]
check("all required files exist", not missing, "missing: " + ", ".join(missing))

# ------------------------------------------------------------------ 2. functions the files call in each other
print("\n[2] Interfaces between the files")
try:
    import database
    needed_db = ["init_db", "create_upload", "get_upload", "create_session", "get_session", "set_status",
                 "add_messages", "get_messages", "save_result", "get_result"]
    absent = [n for n in needed_db if not hasattr(database, n)]
    check("database.py has every function app.py uses", not absent, "missing: " + ", ".join(absent))
except Exception as e:  # noqa: BLE001
    check("database.py imports", False, str(e))

try:
    from ai import ai_module
    needed_ai = ["next_question", "final_score", "fact_check", "mistake_report", "notes_bundle", "full_package"]
    absent = [n for n in needed_ai if not hasattr(ai_module, n)]
    check("ai_module.py has every function the backend uses", not absent, "missing: " + ", ".join(absent))
except Exception as e:  # noqa: BLE001
    check("ai_module.py imports", False, str(e))

try:
    import fake_ai
    absent = [n for n in ["next_question", "final_score", "full_package", "transcribe"] if not hasattr(fake_ai, n)]
    check("fake_ai.py matches the real AI function names", not absent, "missing: " + ", ".join(absent))
except Exception as e:  # noqa: BLE001
    check("fake_ai.py imports", False, str(e))

# ------------------------------------------------------------------ 3. secrets
print("\n[3] Secrets")
env_path = os.path.join(ROOT, ".env")
check(".env exists in the repo root", os.path.exists(env_path), "copy .env.example to .env and add your key")
check("ai/.env does not exist (keep one .env in the root)", not os.path.exists(os.path.join(ROOT, "ai", ".env")),
      "delete ai/.env and keep only the root .env")
try:
    inside = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=ROOT, capture_output=True, text=True)
    if inside.returncode == 0:
        tracked = subprocess.run(["git", "ls-files", "--error-unmatch", ".env"], cwd=ROOT, capture_output=True)
        ignored = subprocess.run(["git", "check-ignore", "-q", ".env"], cwd=ROOT)
        check(".env is ignored by git and not tracked", tracked.returncode != 0 and ignored.returncode == 0,
              "run: git rm --cached .env   and make sure .gitignore contains .env")
    else:
        print("SKIP  not inside a git repository")
except FileNotFoundError:
    print("SKIP  git is not installed or not on PATH")

# ------------------------------------------------------------------ 4. backend with fake AI
print("\n[4] Backend API (fake AI, free)")
res = subprocess.run([sys.executable, os.path.join(BACKEND, "test_api.py")], cwd=ROOT, capture_output=True, text=True)
lines = (res.stdout or "").splitlines()
bad = [l for l in lines if l.startswith("FAIL")]
check("backend/test_api.py passes", res.returncode == 0 and not bad,
      "\n        ".join(bad[:4] + (res.stderr or "").strip().splitlines()[-3:]))


# ------------------------------------------------------------------ 5. real AI through the backend
def run_real():
    print("\n[5] Real AI through the backend (about 2 Gemini requests)")
    os.environ["USE_FAKE_AI"] = "0"
    import io
    import app as backend
    from ai import ai_module as real
    app = backend.app
    check("backend is using the real AI module", backend.ai is real)

    notes = ("Photosynthesis is the process by which plants turn light energy into chemical energy. It happens in "
             "chloroplasts, which contain chlorophyll. In the light-dependent reactions, chlorophyll absorbs sunlight "
             "and splits water, releasing oxygen and producing ATP and NADPH. In the Calvin cycle, the plant uses ATP "
             "and NADPH to turn carbon dioxide into glucose.")
    c = app.test_client()
    up = c.post("/upload", data={"file": (io.BytesIO(notes.encode()), "notes.txt")}, content_type="multipart/form-data")
    sid = c.post("/session/start", json={"upload_id": up.get_json()["upload_id"]}).get_json()["session_id"]

    r = c.post("/session/answer", json={"session_id": sid, "text": "Plants use sunlight to make food in their leaves."})
    body = r.get_data(as_text=True)
    ok = r.status_code == 200 and r.get_json().get("next_question")
    check("AI asks a follow-up question through /session/answer", ok, f"HTTP {r.status_code}: {body.strip()}\n        {hint(body)}")
    if ok:
        print("        AI asked:", r.get_json()["next_question"])
    else:
        return

    r = c.get(f"/session/{sid}/result?mode=score")
    body = r.get_data(as_text=True)
    good = False
    if r.status_code == 200:
        sc = r.get_json()["score"]
        good = (set(sc["scores"]) == {"accuracy", "completeness", "consistency", "clarity"}
                and all(0 <= v["score"] <= 10 for v in sc["scores"].values()) and 0 <= sc["overall"] <= 100)
    check("AI scores the session through /result", good, f"HTTP {r.status_code}: {body.strip()[:300]}\n        {hint(body)}")
    if good:
        print("        overall score:", sc["overall"], "/ 100")


if REAL:
    if failures:
        print("\n[5] Skipped: fix the failures above first (they cost nothing to fix, the real test costs quota).")
    else:
        try:
            run_real()
        except Exception as e:  # noqa: BLE001
            check("real integration ran without crashing", False, f"{e}\n        {hint(str(e))}")

# ------------------------------------------------------------------ verdict
print("\n" + "=" * 60)
if failures:
    print(f"NOT READY: {len(failures)} check(s) failed: {failures}")
    sys.exit(1)
if REAL:
    print("INTEGRATION VERIFIED: Role 1 and Role 3 work together with the real AI. Safe to commit and merge.")
else:
    print("READY TO COMMIT (files, interfaces, secrets and backend all pass).")
    print("Run again with --real once to prove the real AI works through the backend.")
