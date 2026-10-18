/* Every call to the backend, in one place. The endpoints are described in docs/api.md. */
window.Vocalis = window.Vocalis || {};

window.Vocalis.api = (() => {
  const KEY = 'vocalis_token';        // the login token never expires; it is removed only by Log out
  const store = {
    get() { try { return localStorage.getItem(KEY) || ''; } catch (_) { return ''; } },
    set(v) { try { v ? localStorage.setItem(KEY, v) : localStorage.removeItem(KEY); } catch (_) {} }
  };
  // the visitor's own Gemini key: kept only in this browser and sent as a header with each request, never stored on the server
  const GKEY = 'vocalis_gemini_key';
  const keyStore = {
    get() { try { return localStorage.getItem(GKEY) || ''; } catch (_) { return ''; } },
    set(v) { try { v ? localStorage.setItem(GKEY, v) : localStorage.removeItem(GKEY); } catch (_) {} }
  };
  const authHeaders = () => { const h = {}; const t = store.get(); if (t) h.Authorization = 'Bearer ' + t; const k = keyStore.get(); if (k) h['X-Gemini-Key'] = k; return h; };
  let onUnauthorized = () => {};

  async function call(path, opts = {}) {
    const token = store.get();
    const headers = Object.assign({}, opts.headers, authHeaders());
    let res;
    try {
      res = await fetch(API + path, Object.assign({}, opts, { headers }));
    } catch (e) {
      if (e && e.name === 'AbortError') throw e;          // the page cancelled this request on purpose
      throw new Error('Cannot reach the Vocalis server. Check your connection and try again.');
    }
    const isJson = (res.headers.get('content-type') || '').includes('json');
    const data = isJson ? await res.json().catch(() => null) : await res.text();
    if (res.status === 401 && token && !path.startsWith('/auth/')) onUnauthorized();
    if (res.status === 428) { try { window.dispatchEvent(new Event('vocalis:nokey')); } catch (_) {} }
    if (!res.ok) {
      const e = new Error((data && data.error) || 'Something went wrong. Please try again.');
      e.code = data && data.code;
      if (['quota', 'bad_key', 'busy', 'network', 'blocked', 'unknown'].includes(e.code)) { try { window.dispatchEvent(new CustomEvent('vocalis:aierror', { detail: { code: e.code, message: e.message } })); } catch (_) {} }
      throw e;
    }
    if (path.startsWith('/session') || path.startsWith('/upload')) { try { window.dispatchEvent(new Event('vocalis:ai')); } catch (_) {} }
    return data;
  }
  const post = body => ({ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });

  return {
    health: () => call('/health'),
    checkKey: () => call('/key/check', { method: 'POST' }),
    getKey: () => keyStore.get(),
    setKey: k => keyStore.set((k || '').trim()),
    hasToken: () => !!store.get(),
    onUnauthorized: fn => { onUnauthorized = fn; },

    async register(name, email, password) {
      const d = await call('/auth/register', post({ name, email, password }));
      store.set(d.token); return d.user;
    },
    async login(email, password) {
      const d = await call('/auth/login', post({ email, password }));
      store.set(d.token); return d.user;
    },
    async me() { return (await call('/auth/me')).user; },
    async logout() { try { await call('/auth/logout', { method: 'POST' }); } catch (_) {} store.set(''); },

    uploadFile(file) {
      const f = new FormData();
      f.append('file', file, file.name);
      return call('/upload', { method: 'POST', body: f });
    },
    start: (uploadId, topic, timeLimit, confidence) => call('/session/start', post({ upload_id: uploadId, ...(topic ? { topic } : {}), time_limit: timeLimit || 0, confidence })),
    feedback: (id, body) => call('/session/' + id + '/feedback', post(body)),
    stats: () => call('/stats'),
    insights: (query) => call('/insights' + (query || '')),
    feedbackSummary: () => call('/feedback/summary'),
    profile: () => call('/profile'),

    /** One answer: any mix of text, a voice recording (audio Blob) and a whiteboard drawing (PNG Blob). */
    answer(sessionId, { text, audio, drawing, integrity }, signal) {
      const f = new FormData();
      f.append('session_id', sessionId);
      if (text) f.append('text', text);
      if (audio) f.append('audio', audio, 'answer.wav');
      if (drawing) f.append('drawing', drawing, 'whiteboard.png');
      if (integrity) { f.append('paste_attempts', integrity.paste); f.append('tab_switches', integrity.tabs); }
      return call('/session/answer', { method: 'POST', body: f, signal });
    },

    finish: id => call('/session/' + id + '/finish', { method: 'POST' }),
    session: id => call('/session/' + id),
    sessions: () => call('/sessions'),
    progress: (id) => call('/session/' + id + '/progress'),
    result: (id, mode, lang) => call('/session/' + id + '/result?mode=' + mode + '&lang=' + encodeURIComponent(lang || 'Kannada')),
    report: id => call('/session/' + id + '/report'),
    async exportDoc(sessionId, kind) {      // Word report as a blob
      const res = await fetch(API + '/session/' + sessionId + '/export?kind=' + kind, { headers: authHeaders() });
      if (!res.ok) { let m = 'Could not create the Word file.'; try { m = (await res.json()).error || m; } catch (_) {} throw new Error(m); }
      return res.blob();
    },
    async tts(text, voice, signal) {        // AI voice: returns a WAV blob URL
      const res = await fetch(API + '/tts', Object.assign(post({ text, voice }), { signal, headers: Object.assign({ 'Content-Type': 'application/json' }, authHeaders()) }));
      if (!res.ok) { let m = 'AI voice unavailable'; try { m = (await res.json()).error || m; } catch (_) {} throw new Error(m); }
      return URL.createObjectURL(await res.blob());
    },
    async drawingUrl(messageId) {          // images need the login header, so fetch them as a blob
      const res = await fetch(API + '/message/' + messageId + '/drawing', { headers: authHeaders() });
      if (!res.ok) throw new Error('drawing unavailable');
      return URL.createObjectURL(await res.blob());
    }
  };
})();
