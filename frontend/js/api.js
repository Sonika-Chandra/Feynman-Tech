/* Every call to the backend, in one place. The endpoints are described in docs/api.md. */
window.Vocalis = window.Vocalis || {};

window.Vocalis.api = (() => {
  const KEY = 'vocalis_token';        // the login token never expires; it is removed only by Log out
  const store = {
    get() { try { return localStorage.getItem(KEY) || ''; } catch (_) { return ''; } },
    set(v) { try { v ? localStorage.setItem(KEY, v) : localStorage.removeItem(KEY); } catch (_) {} }
  };
  let onUnauthorized = () => {};

  async function call(path, opts = {}) {
    const headers = Object.assign({}, opts.headers);
    const token = store.get();
    if (token) headers.Authorization = 'Bearer ' + token;
    let res;
    try {
      res = await fetch(API + path, Object.assign({}, opts, { headers }));
    } catch (e) {
      throw new Error('Cannot reach the backend. Start it with: python backend/app.py');
    }
    const isJson = (res.headers.get('content-type') || '').includes('json');
    const data = isJson ? await res.json().catch(() => null) : await res.text();
    if (res.status === 401 && token && !path.startsWith('/auth/')) onUnauthorized();
    if (!res.ok) throw new Error((data && data.error) || ('The backend returned an error (' + res.status + ').'));
    return data;
  }
  const post = body => ({ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });

  return {
    health: () => call('/health'),
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
    start: (uploadId, topic) => call('/session/start', post(topic ? { upload_id: uploadId, topic } : { upload_id: uploadId })),

    /** One answer: any mix of text, a voice recording (audio Blob) and a whiteboard drawing (PNG Blob). */
    answer(sessionId, { text, audio, drawing }) {
      const f = new FormData();
      f.append('session_id', sessionId);
      if (text) f.append('text', text);
      if (audio) f.append('audio', audio, 'answer.wav');
      if (drawing) f.append('drawing', drawing, 'whiteboard.png');
      return call('/session/answer', { method: 'POST', body: f });
    },

    finish: id => call('/session/' + id + '/finish', { method: 'POST' }),
    session: id => call('/session/' + id),
    sessions: () => call('/sessions'),
    result: (id, mode, lang) => call('/session/' + id + '/result?mode=' + mode + '&lang=' + encodeURIComponent(lang || 'Kannada')),
    report: id => call('/session/' + id + '/report'),
    async exportDoc(sessionId, kind) {      // Word report as a blob
      const res = await fetch(API + '/session/' + sessionId + '/export?kind=' + kind, { headers: { Authorization: 'Bearer ' + store.get() } });
      if (!res.ok) { let m = 'Could not create the Word file.'; try { m = (await res.json()).error || m; } catch (_) {} throw new Error(m); }
      return res.blob();
    },
    async tts(text, voice) {                // AI voice: returns a WAV blob URL
      const res = await fetch(API + '/tts', Object.assign(post({ text, voice }), { headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + store.get() } }));
      if (!res.ok) { let m = 'AI voice unavailable'; try { m = (await res.json()).error || m; } catch (_) {} throw new Error(m); }
      return URL.createObjectURL(await res.blob());
    },
    async drawingUrl(messageId) {          // images need the login header, so fetch them as a blob
      const res = await fetch(API + '/message/' + messageId + '/drawing', { headers: { Authorization: 'Bearer ' + store.get() } });
      if (!res.ok) throw new Error('drawing unavailable');
      return URL.createObjectURL(await res.blob());
    }
  };
})();
