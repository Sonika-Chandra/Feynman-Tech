# Putting Vocalis online (optional)

The app is one Flask process that also serves the web page, so any host that runs Python works. These steps use **Render** (free plan, gives an https address, which the microphone needs).

## 1. Push the code to GitHub
The repo must contain `Procfile`, `render.yaml` and `requirements.txt` (they are in the project). Never commit `.env`.

## 2. Create the service
1. Sign up at render.com with your GitHub account.
2. **New +  ->  Blueprint**, pick this repository. Render reads `render.yaml` and creates the web service.
3. When asked for `FEEDBACK_KEY`, type any long random text. You will use it to download the feedback CSV.
   **Do not add a `GEMINI_API_KEY`.** Without a server key, every visitor must paste their own free Gemini key on the site, so each person uses their own daily allowance and you never run out of quota.
4. Wait for the first deploy (a few minutes). Your site appears at `https://vocalis-xxxx.onrender.com`.

(Manual alternative: New + -> Web Service -> build command `pip install -r requirements.txt`, start command `gunicorn --chdir backend app:app --bind 0.0.0.0:$PORT --workers 1 --threads 8 --timeout 180`, then add the environment variables below.)

## 3. Environment variables
| Name | Value | Why |
|---|---|---|
| `GEMINI_API_KEY` | leave unset | visitors bring their own key (set it only if you want to pay for everyone's use) |
| `PUBLIC` | `1` | hides the key ending in `/health` |
| `DAILY_AI_LIMIT` | not needed | only applies to a server key you provide |
| `FEEDBACK_KEY` | any long random text | lets you download all student feedback at `/feedback/export.csv?key=YOUR_KEY` (without it, the download is blocked on the public site) |
| `PYTHON_VERSION` | `3.12.7` | Render's Python version |

## 4. Know the free-plan behaviour
- The service **sleeps after ~15 minutes** without visitors; the first visit afterwards takes about a minute to wake. Open the site yourself just before judging.
- The disk is **not permanent**: accounts and sessions are cleared when the service restarts or redeploys. That is fine for a demo; for real use add a Render disk or a hosted database and set `DATABASE_PATH`.
- With visitors' own keys the quota is theirs: about 20 requests per model per day on a free key, and one session uses 8. Tell testers this, and to check the request counter in the top bar. (If you do set a server key, its quota is shared by everyone.) If it runs out, the app shows a clear error. Lower `DAILY_AI_LIMIT` so one visitor cannot use it all, list fallback models in `GEMINI_FALLBACK_MODELS`, or enable billing on the key's Google Cloud project. Keep a recorded demo video as a backup.

## 4a. Editing the code after you have deployed
Yes, deploy first and keep editing. Render watches your GitHub branch: change the code locally, test it with `python backend/app.py`, then
```
git add .
git commit -m "describe the change"
git push
```
and Render rebuilds and redeploys by itself in a few minutes (watch the **Events** tab). The link stays the same. Two cautions:
- **Every redeploy restarts the server, and on the free plan that wipes accounts, sessions and feedback.** Download `/feedback/export.csv?key=...` and screenshot `/#impact` before you push, and avoid pushing while people are testing.
- Push only changes you have tested locally. If a deploy breaks the site, open the failed deploy on Render and use **Rollback** to the last good one. Stop editing about an hour before the deadline and re-test the live URL once.

## 4b. When a visitor runs out in the middle of a session
The page opens the key box by itself, with a short message. The visitor pastes a key from a different Google account or project, and as soon as it tests fine the page repeats the step that failed (their typed answer is still in the box, so nothing is lost). Everything answered so far is already saved on the server, so even if they close the tab, **Continue** on the home screen reopens the same session. This works as long as the server has not restarted (see the free-plan note above).

## 5. About API keys
- Visitors paste their own key in the browser; it is never stored on the server. If you also set a `GEMINI_API_KEY` of your own, keep it only in the host's environment variables, never in the repo, a screenshot, the slides or the README.
- Do not try to create many keys to get around the daily limit. That goes against Google's terms and can get the projects blocked. The right fixes are each visitor using their own key (built in), the per-user cap on a server key, asking fewer questions per session, or enabling billing.
- If a key is ever exposed, delete it in Google AI Studio and create a new one.

## 5b. Feedback and the Impact page
- Rating a session is **required**: on the report page the student must tap one star (it saves at once) before they can leave, download or start another test. Everything else on the form is optional.
- **Impact page:** open `https://YOUR-SITE/#impact` (also the **Impact** link in the top bar and on the login page). It draws, with no login needed and no personal data: score spread, weakest criterion, usefulness stars, would-recommend, confidence before vs real score vs after, retry gains per topic, tags tapped, badges, flagged share and sessions per day. Screenshot it for the slides and the video.
- **Totals for a period (for example a 3-hour pilot):** on the Impact page choose **Last 3 hours**, or set an exact From / To range (your own time zone). Every chart and the CSV download then cover only that window. By URL: `/insights?hours=3`, `/feedback/export.csv?key=KEY&hours=3`, or `?since=2026-10-18T10:00:00Z&until=2026-10-18T13:00:00Z`.
- **Team key:** it is the `FEEDBACK_KEY` you typed in Render (Dashboard → your service → Environment). On the Impact page type it into the "Team key" box and press **Download feedback (CSV)**. Share it only inside the team.
- **Raw data:** `/insights` (JSON for the charts) and `/feedback/export.csv?key=YOUR_FEEDBACK_KEY` (one row per session with comments). Download the CSV before the free plan restarts, because the database is wiped on restart.

## 6. Check it
Open the URL, create an account, click **API key** and paste your own key (aistudio.google.com/apikey), then upload `test-material/photosynthesis.md`, and run one full session. Put the URL in `submission.md` and the README.
