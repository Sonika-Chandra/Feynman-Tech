"""
Tests the whole API without a browser.   Run from the repo root:
    python backend/test_api.py            # uses the fake AI: free, instant
    python backend/test_api.py --real     # uses Gemini: costs about 12 requests of your daily quota
"""
import io
import os
import sys
import tempfile

REAL = "--real" in sys.argv
os.environ["USE_FAKE_AI"] = "0" if REAL else "1"   # overrides anything in .env
print("MODE:", "REAL Gemini (uses your quota)" if REAL else "FAKE AI (free)", "\n")
os.environ["DATABASE_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app  # noqa: E402

NOTES = (
    "Photosynthesis is the process by which plants turn light energy into chemical energy. It happens in "
    "chloroplasts, which contain chlorophyll. In the light-dependent reactions, chlorophyll absorbs sunlight and "
    "splits water, releasing oxygen and producing ATP and NADPH. In the Calvin cycle, the plant uses ATP and NADPH "
    "to turn carbon dioxide into glucose."
)
client = app.test_client()
failures = []


def check(name, condition, detail=""):
    print(("PASS  " if condition else "FAIL  ") + name + (f"   {detail}" if not condition else ""))
    if not condition:
        failures.append(name)


r = client.get("/health")
check("health", r.status_code == 200 and r.get_json()["status"] == "ok")
check("AI mode matches the flag", r.get_json()["fake_ai"] == (not REAL), str(r.get_json()))

r = client.post("/upload")
check("upload with no file -> 400", r.status_code == 400)

r = client.post("/upload", data={"file": (io.BytesIO(b"x"), "evil.exe")}, content_type="multipart/form-data")
check("upload wrong file type -> 400", r.status_code == 400)

r = client.post("/upload", data={"file": (io.BytesIO(NOTES.encode()), "notes.txt")}, content_type="multipart/form-data")
check("upload notes.txt -> 201", r.status_code == 201, r.get_data(as_text=True))
if r.status_code != 201:
    sys.exit("Cannot continue: upload failed (see the line above).")
upload_id = r.get_json()["upload_id"]

r = client.post("/session/start", json={"upload_id": 9999})
check("start with unknown upload -> 404", r.status_code == 404)

r = client.post("/session/start", json={"upload_id": upload_id})
check("start session -> 201", r.status_code == 201, r.get_data(as_text=True))
if r.status_code != 201:
    sys.exit("Cannot continue: session start failed (see the line above).")
sid = r.get_json()["session_id"]

r = client.post("/session/answer", json={"session_id": sid, "text": ""})
check("empty answer -> 400", r.status_code == 400)

rounds, last, loop_error = 0, None, None
reply = "Plants turn sunlight into food using chlorophyll in chloroplasts."
for i in range(8):
    r = client.post("/session/answer", json={"session_id": sid, "text": reply})
    if r.status_code != 200:
        loop_error = f"HTTP {r.status_code}: {r.get_data(as_text=True).strip()}"
        break
    last = r.get_json()
    if last["should_stop"]:
        break
    rounds += 1
    reply = f"My answer number {i + 2}: water is split and oxygen is released."
check("answer endpoint works", loop_error is None, loop_error)
check("loop stops by itself", last is not None and last["should_stop"], str(last))
check("at most 5 questions asked", 1 <= rounds <= 5, f"rounds={rounds}")

r = client.post("/session/answer", json={"session_id": sid, "text": "one more"})
check("answer after finished -> 409", r.status_code == 409)

r = client.get(f"/session/{sid}")
msgs = r.get_json()["messages"]
check("messages saved in order", len(msgs) >= 2 and msgs[0]["role"] == "student" and msgs[1]["role"] == "ai",
      f"found {len(msgs)} saved messages: {msgs[:2]}")

r = client.get(f"/session/{sid}/report")
check("report before result -> 404", r.status_code == 404)

r = client.get(f"/session/{sid}/result")
pkg = r.get_json() if r.status_code == 200 else {}
check("result -> 200", r.status_code == 200, r.get_data(as_text=True)[:300])
check("result has score fields", set(pkg.get("score", {}).get("scores", {})) == {"accuracy", "completeness", "consistency", "clarity"})
check("result has overall 0-100", 0 <= pkg.get("score", {}).get("overall", -1) <= 100)

r = client.get(f"/session/{sid}/report")
body = r.get_data(as_text=True)
check("report has fixed headings", all(h in body for h in ("### Concept Misunderstood", "### Correct Explanation", "### Recommended Review")))

r = client.get(f"/session/{sid}/report?download=1")
check("report download header", "attachment" in r.headers.get("Content-Disposition", ""))

r = client.get("/nope")
check("unknown route -> JSON 404", r.status_code == 404 and "error" in r.get_json())

print("\n" + ("ALL TESTS PASSED" if not failures else f"{len(failures)} FAILED: {failures}"))
sys.exit(1 if failures else 0)
