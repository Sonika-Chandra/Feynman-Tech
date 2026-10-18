Optional browser-flow test (needs Node.js). It loads the real page in jsdom and clicks through
register, upload, five questions with a whiteboard drawing, the report, re-upload, logout and login.

    npm install jsdom@24            (inside this folder)
    set USE_FAKE_AI=1  and start    python backend/app.py        (a fresh database: delete backend/feynman.db first)
    node e2e.js                     (set PORT=5000 if you use the default port)
