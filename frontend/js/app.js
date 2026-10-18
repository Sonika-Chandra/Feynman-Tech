/* Vocalis single-page app: login → home → topics → chat (AI asks, whiteboard when needed) → report. */
(() => {
  const V = window.Vocalis;
  const $ = id => document.getElementById(id);
  const SCREENS = ['auth', 'home', 'topics', 'chat', 'report', 'about'];
  const TOTAL = 5;

  const state = {
    user: null, upload: null, topic: null, sessionId: null, round: 1, busy: false,
    pendingAudio: null, reportMd: '', reportBasic: false, authMode: 'login', score: null, mistakes: [], notesMd: ''
  };

  // ---------------------------------------------------------------- settings (remembered on this device)
  const opts = { timeLimit: 0, speechLang: 'en-IN', accurate: false, speak: false, voiceEngine: 'ai', aiVoice: 'Aoede', devVoice: '' };
  function loadOpts() {
    try { Object.assign(opts, JSON.parse(localStorage.getItem('vocalis_opts') || '{}')); } catch (_) {}
  }
  function saveOpts() { try { localStorage.setItem('vocalis_opts', JSON.stringify(opts)); } catch (_) {} }
  function paintOpts() {
    document.querySelectorAll('#timeChips .chip-btn').forEach(b => b.classList.toggle('active', +b.dataset.sec === opts.timeLimit));
    $('speechLang').value = opts.speechLang; $('optAccurate').checked = opts.accurate; $('optSpeak').checked = opts.speak;
    $('speakToggle').setAttribute('aria-pressed', opts.speak);
    $('voiceEngine').value = opts.voiceEngine; fillVoices();
    $('voiceBox').style.display = opts.speak ? '' : 'none';
  }
  document.querySelectorAll('#timeChips .chip-btn').forEach(b => b.addEventListener('click', () => { opts.timeLimit = +b.dataset.sec; saveOpts(); paintOpts(); }));
  $('speechLang').addEventListener('change', e => { opts.speechLang = e.target.value; saveOpts(); });
  $('optAccurate').addEventListener('change', e => { opts.accurate = e.target.checked; saveOpts(); });
  $('optSpeak').addEventListener('change', e => { opts.speak = e.target.checked; saveOpts(); paintOpts(); });
  $('speakToggle').addEventListener('click', () => { opts.speak = !opts.speak; saveOpts(); paintOpts(); if (!opts.speak) stopSpeaking(); });

  // ---------------------------------------------------------------- voices
  const AI_VOICES = [['Aoede', 'Aoede – breezy, friendly'], ['Kore', 'Kore – clear, confident'], ['Leda', 'Leda – youthful'],
                     ['Zephyr', 'Zephyr – bright'], ['Puck', 'Puck – upbeat'], ['Charon', 'Charon – calm, informative']];
  function deviceVoices() { try { return (window.speechSynthesis && speechSynthesis.getVoices()) || []; } catch (_) { return []; } }
  function voiceScore(v) {                 // prefers the natural/neural voices that sound most like an AI assistant
    const n = v.name.toLowerCase();
    let sc = 0;
    if (/natural|neural|online/.test(n)) sc += 50;
    if (/aria|jenny|sonia|neerja|swara|libby|google|samantha|siri|ava|allison|zira/.test(n)) sc += 20;
    if (v.lang && v.lang.toLowerCase() === opts.speechLang.toLowerCase()) sc += 30;
    else if (v.lang && v.lang.slice(0, 2) === opts.speechLang.slice(0, 2)) sc += 15;
    if (!v.localService) sc += 5;
    return sc;
  }
  function bestDeviceVoice() {
    if (opts.devVoice) { const f = deviceVoices().find(v => v.name === opts.devVoice); if (f) return f; }
    return deviceVoices().slice().sort((a, b) => voiceScore(b) - voiceScore(a))[0] || null;
  }
  function fillVoices() {
    const sel = $('voiceName'); sel.innerHTML = '';
    if (opts.voiceEngine === 'ai') {
      AI_VOICES.forEach(([id, label]) => sel.add(new Option(label, id)));
      sel.value = opts.aiVoice;
    } else {
      sel.add(new Option('Automatic (most natural available)', ''));
      deviceVoices().slice().sort((a, b) => voiceScore(b) - voiceScore(a)).forEach(v => sel.add(new Option(v.name + ' (' + v.lang + ')', v.name)));
      sel.value = opts.devVoice;
    }
  }
  try { window.speechSynthesis && (speechSynthesis.onvoiceschanged = fillVoices); } catch (_) {}
  $('voiceEngine').addEventListener('change', e => { opts.voiceEngine = e.target.value; saveOpts(); fillVoices(); });
  $('voiceName').addEventListener('change', e => { if (opts.voiceEngine === 'ai') opts.aiVoice = e.target.value; else opts.devVoice = e.target.value; saveOpts(); });
  $('voicePreview').addEventListener('click', () => speakNow('Hello! I will ask you five questions about your topic. Explain each one in your own words.', () => {}));

  // ---------------------------------------------------------------- helpers
  function show(name) {
    SCREENS.forEach(n => $('screen-' + n).hidden = n !== name);
    $('topbar').hidden = name === 'auth' || (name === 'about' && !state.user);
    document.querySelectorAll('.nav-link').forEach(b => b.classList.toggle('active', b.dataset.nav === name || (b.dataset.nav === 'home' && ['topics', 'report'].includes(name))));
    V.orb.enable(name === 'chat');
    const badge = $('modeBadge');
    if (name === 'auth') { document.body.appendChild(badge); badge.classList.remove('in-topbar'); }
    else { $('topbarRight').prepend(badge); badge.classList.add('in-topbar'); }
    if (name !== 'chat') { stopTimer(); stopSpeaking(); }
    window.scrollTo(0, 0);
  }
  let toastTimer;
  function toast(msg) {
    const t = $('toast'); t.textContent = msg; t.hidden = false;
    clearTimeout(toastTimer); toastTimer = setTimeout(() => t.hidden = true, 5000);
  }
  const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const lang = () => $('langSelect').value;
  const svgUrl = svg => 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);

  /** Small markdown renderer (headings, bullets, bold, rules). Gap blocks become cards. */
  function inline(t) {
    return esc(t).replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>').replace(/`(.+?)`/g, '<code>$1</code>')
      .replace(/(^|[^*])\*(?!\s)(.+?)\*/g, '$1<em>$2</em>');
  }
  function md(text) {
    const out = []; let list = false, card = false;
    const closeList = () => { if (list) { out.push('</ul>'); list = false; } };
    const closeCard = () => { closeList(); if (card) { out.push('</div>'); card = false; } };
    String(text || '').split(/\r?\n/).forEach(line => {
      const l = line.trimEnd();
      if (/^---+$/.test(l.trim())) { closeCard(); return; }
      let m;
      if ((m = l.match(/^(#{1,4})\s+(.*)$/))) {
        closeList();
        const lvl = m[1].length;
        if (lvl === 3 && /^concept misunderstood/i.test(m[2]) && !card) { out.push('<div class="gap-card">'); card = true; }
        else if (lvl <= 2) closeCard();
        out.push(`<h${lvl}>${inline(m[2])}</h${lvl}>`);
        return;
      }
      if ((m = l.match(/^\s*(?:[-*•]|\d+\.)\s+(.*)$/))) {
        if (!list) { out.push('<ul>'); list = true; }
        out.push(`<li>${inline(m[1])}</li>`); return;
      }
      closeList();
      if (l.trim()) out.push(`<p>${inline(l)}</p>`);
    });
    closeCard();
    return out.join('');
  }

  // ================================================================ login
  function setAuthMode(mode) {
    state.authMode = mode;
    document.querySelectorAll('.seg-btn').forEach(b => b.classList.toggle('active', b.dataset.mode === mode));
    $('nameField').hidden = mode !== 'register';
    $('authSubmit').textContent = mode === 'login' ? 'Log in' : 'Create account';
    $('authPassword').autocomplete = mode === 'login' ? 'current-password' : 'new-password';
    $('authError').textContent = '';
  }
  document.querySelectorAll('.seg-btn').forEach(b => b.addEventListener('click', () => setAuthMode(b.dataset.mode)));

  $('authForm').addEventListener('submit', async e => {
    e.preventDefault();
    const email = $('authEmail').value.trim(), password = $('authPassword').value, name = $('authName').value.trim();
    $('authError').textContent = '';
    if (!email || !password) { $('authError').textContent = 'Enter your email and password.'; return; }
    $('authSubmit').disabled = true;
    try {
      state.user = state.authMode === 'login' ? await V.api.login(email, password) : await V.api.register(name, email, password);
      $('authPassword').value = '';
      await enterHome();
    } catch (err) {
      $('authError').textContent = err.message;
    } finally { $('authSubmit').disabled = false; }
  });

  async function logout() {
    await V.api.logout();
    state.user = null; state.sessionId = null;
    show('auth'); setAuthMode('login');
  }
  $('logoutBtn').addEventListener('click', logout);
  V.api.onUnauthorized(() => { state.user = null; show('auth'); toast('Please log in again.'); });
  document.querySelectorAll('.nav-link').forEach(b => b.addEventListener('click', () => {
    if (!state.user) return;
    b.dataset.nav === 'about' ? show('about') : enterHome();
  }));
  $('aboutFromAuth').addEventListener('click', () => show('about'));
  $('aboutBack').addEventListener('click', () => state.user ? enterHome() : show('auth'));
  $('aboutStart').addEventListener('click', () => state.user ? enterHome() : show('auth'));
  $('brandLink').addEventListener('click', e => { e.preventDefault(); if (state.user && $('screen-chat').hidden) enterHome(); });

  // ================================================================ home
  async function enterHome() {
    $('userChip').textContent = state.user.name;
    $('userAvatar').textContent = (state.user.name.trim()[0] || '?').toUpperCase();
    $('homeTitle').textContent = 'Hello, ' + state.user.name.split(' ')[0] + '. What will you teach today?';
    $('uploadError').textContent = '';
    show('home');
    loadHistory();
  }

  async function loadHistory() {
    const box = $('historyList');
    box.innerHTML = '<div class="skeleton"></div><div class="skeleton"></div>';
    try {
      const { sessions } = await V.api.sessions();
      if (!sessions.length) { box.innerHTML = '<p class="history-empty">No sessions yet. Upload something to begin.</p>'; return; }
      box.innerHTML = '';
      sessions.forEach(s => {
        const b = document.createElement('button');
        b.className = 'h-item';
        const when = new Date(s.created_at.replace(' ', 'T') + 'Z');
        b.innerHTML = `<span><b>${esc(s.topic)}</b><small>${esc(s.filename)} · ${isNaN(when) ? '' : when.toLocaleDateString()}</small></span>` +
          (s.overall != null ? `<span class="pill">${s.overall}</span>` : `<span class="pill live">${s.status === 'active' ? 'Continue' : 'View'}</span>`);
        b.addEventListener('click', () => s.status === 'active' ? resumeChat(s.session_id) : openReport(s.session_id, s.topic));
        box.appendChild(b);
      });
    } catch (err) { box.innerHTML = `<p class="history-empty">${esc(err.message)}</p>`; }
  }

  // ---- upload
  const drop = $('drop'), fileInput = $('fileInput');
  const openPicker = () => { if (!drop.classList.contains('busy')) fileInput.click(); };
  drop.addEventListener('click', e => { if (e.target.id !== 'chooseBtn') openPicker(); });
  $('chooseBtn').addEventListener('click', e => { e.stopPropagation(); openPicker(); });
  drop.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openPicker(); } });
  ['dragenter', 'dragover'].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.add('over'); }));
  ['dragleave', 'drop'].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.remove('over'); }));
  drop.addEventListener('drop', e => { if (e.dataTransfer.files[0]) handleUpload(e.dataTransfer.files[0]); });
  fileInput.addEventListener('change', () => { if (fileInput.files[0]) handleUpload(fileInput.files[0]); fileInput.value = ''; });

  async function handleUpload(file) {
    $('uploadError').textContent = '';
    drop.classList.add('busy');
    $('dropTitle').textContent = 'Reading ' + file.name + '…';
    try {
      state.upload = await V.api.uploadFile(file);
      renderTopics();
    } catch (err) {
      $('uploadError').textContent = err.message;
      if (state.user && $('screen-home').hidden) show('home');
    } finally {
      drop.classList.remove('busy');
      $('dropTitle').textContent = 'Drop a file here or click to choose';
    }
  }

  // ================================================================ topics
  function renderTopics() {
    const u = state.upload;
    $('topicsFile').textContent = u.filename;
    $('startError').textContent = '';
    paintOpts();
    const grid = $('topicGrid'); grid.innerHTML = '';
    u.sections.forEach((sec, i) => {
      const b = document.createElement('button');
      b.className = 'topic';
      b.innerHTML = `<span class="num">${i + 1}</span><h4>${esc(sec.title.replace(/^\s*(\d+(\.\d+)*[.)]|[IVXLC]+\.)\s+/, ''))}</h4><p>${esc(sec.preview)}</p><span class="go">Test me on this →</span>`;
      b.addEventListener('click', () => { b.classList.add('busy'); startSession(sec.title).finally(() => b.classList.remove('busy')); });
      grid.appendChild(b);
    });
    $('wholeDocBtn').style.display = u.sections.length > 1 ? '' : 'none';
    show('topics');
  }
  $('topicsBack').addEventListener('click', enterHome);
  $('wholeDocBtn').addEventListener('click', () => startSession(null));

  async function startSession(topic) {
    $('startError').textContent = '';
    try {
      const s = await V.api.start(state.upload.upload_id, topic);
      state.topic = topic;
      openChat(s.session_id, s.topic, s.round, [{ role: 'ai', text: s.next_question, needs_whiteboard: s.needs_whiteboard, diagram_svg: s.diagram_svg }]);
    } catch (err) {
      $('startError').textContent = err.message;
      toast(err.message);
    }
  }

  // ================================================================ timer (per question)
  const timer = { id: null, end: 0, total: 0 };
  function stopTimer() { clearInterval(timer.id); timer.id = null; $('timer').hidden = true; $('timer').classList.remove('warn'); }
  function startTimer() {
    stopTimer();
    if (!opts.timeLimit) return;
    timer.total = opts.timeLimit * 1000; timer.end = Date.now() + timer.total;
    $('timer').hidden = false;
    timer.id = setInterval(tick, 250); tick();
  }
  function tick() {
    const left = timer.end - Date.now();
    if (left <= 0) { stopTimer(); toast('Time is up for this question.'); send({ timeout: true }); return; }
    const s = Math.ceil(left / 1000);
    $('timerText').textContent = Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0');
    $('timerBar').style.width = (left / timer.total * 100) + '%';
    $('timer').classList.toggle('warn', left <= 10000);
  }

  // ================================================================ read questions aloud
  let voiceAudio = null;
  function stopSpeaking() {
    try { window.speechSynthesis && window.speechSynthesis.cancel(); } catch (_) {}
    if (voiceAudio) { try { voiceAudio.pause(); } catch (_) {} voiceAudio = null; }
  }
  function speakDevice(text, done) {
    if (!window.speechSynthesis) { done(); return; }
    const u = new SpeechSynthesisUtterance(text);
    const v = bestDeviceVoice();
    if (v) { u.voice = v; u.lang = v.lang; } else u.lang = opts.speechLang;
    u.rate = 1; u.pitch = 1;
    let finished = false;
    const end = () => { if (finished) return; finished = true; V.orb.setMode('idle'); done(); };
    u.onstart = () => V.orb.setMode('speaking');
    u.onend = end; u.onerror = end;
    window.speechSynthesis.speak(u);
    setTimeout(() => { if (!finished && !window.speechSynthesis.speaking) end(); }, 1500);
  }
  async function speakNow(text, done) {
    stopSpeaking();
    if (opts.voiceEngine === 'ai') {
      try {
        const url = await V.api.tts(text, opts.aiVoice);
        const a = new Audio(url); voiceAudio = a;
        let finished = false;
        const end = () => { if (finished) return; finished = true; V.orb.setMode('idle'); voiceAudio = null; done(); };
        a.onended = end; a.onerror = end;
        V.orb.setMode('speaking');
        await a.play();
        return;
      } catch (err) {
        voiceAudio = null; V.orb.setMode('idle');
        if (!speakNow.warned) { speakNow.warned = true; toast('AI voice unavailable, using the device voice instead.'); }
      }
    }
    speakDevice(text, done);
  }
  function speak(text, done) {
    if (!opts.speak) { done(); return; }
    speakNow(text, done);
  }

  // ================================================================ chat
  function setDots(round) {
    const d = $('roundDots'); d.innerHTML = '';
    for (let i = 1; i <= TOTAL; i++) d.insertAdjacentHTML('beforeend', `<i class="${i < round ? 'done' : i === round ? 'now' : ''}"></i>`);
    $('chatRoundLabel').textContent = `Question ${Math.min(round, TOTAL)} of ${TOTAL}`;
  }

  function addBubble(role, text, extra = {}) {
    const row = document.createElement('div');
    row.className = 'msg ' + (role === 'ai' ? 'ai' : 'me');
    const av = role === 'ai' ? '<div class="avatar">V</div>' : '';
    row.innerHTML = `${av}<div class="bubble"></div>`;
    const b = row.querySelector('.bubble');
    if (extra.label) b.insertAdjacentHTML('afterbegin', `<span class="qn">${esc(extra.label)}</span>`);
    const body = document.createElement('span'); body.className = 'body'; body.textContent = text; b.appendChild(body);
    if (extra.diagram) { const img = document.createElement('img'); img.src = svgUrl(extra.diagram); img.alt = 'Diagram to label'; b.appendChild(img); }
    if (extra.needsWhiteboard) b.insertAdjacentHTML('beforeend', `<br><span class="wb-tag">✎ ${extra.diagram ? 'Name the parts on the whiteboard' : 'Use the whiteboard to answer this'}</span>`);
    if (extra.imageUrl) { const img = document.createElement('img'); img.src = extra.imageUrl; img.alt = 'Your whiteboard drawing'; b.appendChild(img); }
    $('thread').appendChild(row);
    $('thread').scrollTop = $('thread').scrollHeight;
    return row;
  }
  function typing() {
    const row = document.createElement('div');
    row.className = 'msg ai';
    row.innerHTML = '<div class="avatar">V</div><div class="bubble"><span class="typing"><i></i><i></i><i></i></span></div>';
    $('thread').appendChild(row); $('thread').scrollTop = $('thread').scrollHeight;
    return row;
  }

  function setWb(open, hint) {
    $('chatLayout').classList.toggle('wb-open', open);
    $('wbToggle').setAttribute('aria-pressed', open);
    if (hint) $('wbHint').textContent = hint;
    if (open) requestAnimationFrame(() => V.whiteboard.resize());
  }
  $('wbToggle').addEventListener('click', () => setWb(!$('chatLayout').classList.contains('wb-open')));
  $('wbClose').addEventListener('click', () => setWb(false));

  /** Everything that happens when a new question appears: whiteboard, diagram, reading aloud, then the timer. */
  function presentQuestion(q) {
    V.whiteboard.clear();
    V.whiteboard.setDiagram(q.diagram_svg || '');
    const hint = q.diagram_svg ? 'Name the numbered parts: use Mark & name or Text, then press Send.'
      : q.needs_whiteboard ? 'This question needs a drawing. Sketch, label or plot it here.' : 'Draw, label or plot your answer. It is sent with your reply.';
    setWb(!!q.needs_whiteboard, hint);
    V.orb.setMode('idle');
    state.busy = false; setComposer(true); $('answerBox').focus();
    speak(q.text, startTimer);
  }

  function openChat(sessionId, topic, round, messages) {
    state.sessionId = sessionId; state.round = round; state.busy = false;
    $('chatTopic').textContent = topic;
    $('thread').innerHTML = ''; $('answerBox').value = ''; clearAudio();
    setDots(round);
    let q = 0;
    messages.forEach(m => {
      if (m.role === 'ai') { q++; addBubble('ai', m.text, { label: 'Question ' + q, needsWhiteboard: m.needs_whiteboard, diagram: m.diagram_svg }); }
      else addBubble('me', m.text.split('\n\n[Whiteboard drawing]')[0]);
    });
    show('chat');
    const last = messages[messages.length - 1];
    if (last && last.role === 'ai') presentQuestion({ text: last.text, needs_whiteboard: last.needs_whiteboard, diagram_svg: last.diagram_svg });
  }

  async function resumeChat(id) {
    try {
      const info = await V.api.session(id);
      state.upload = null; state.topic = info.topic;
      openChat(id, info.topic, info.round, info.messages);
    } catch (err) { toast(err.message); }
  }

  function setComposer(enabled) {
    ['answerBox', 'sendBtn', 'micBtn', 'wbToggle'].forEach(i => $(i).disabled = !enabled);
  }
  function clearAudio() {
    state.pendingAudio = null; $('attachRow').innerHTML = ''; $('attachRow').hidden = true; $('micStatus').hidden = true;
  }
  function showAudioChip(accurate) {
    const row = $('attachRow'); row.hidden = false;
    row.innerHTML = '<span class="chip">🎙 ' + (accurate ? 'Recording attached: Gemini will transcribe it for accuracy.' : 'Recording attached.') +
      ' <button title="Remove, send the text instead" aria-label="Remove recording">✕ Remove</button></span>';
    row.querySelector('button').addEventListener('click', clearAudio);
  }

  const box = $('answerBox');
  box.addEventListener('input', () => {
    box.style.height = 'auto'; box.style.height = Math.min(box.scrollHeight, 160) + 'px';
    // Editing the text after a recording means "send my text": drop the attached recording.
    if (state.pendingAudio && box.value.trim() !== mic.live.trim()) { clearAudio(); toast('Sending your edited text instead of the recording.'); }
  });
  box.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } });
  $('sendBtn').addEventListener('click', () => send());

  // ---- voice: the microphone feeds the orb, a recording (for accurate mode) and live browser speech-to-text
  const mic = { on: false, stream: null, ctx: null, mr: null, chunks: [], speech: false, base: '', live: '' };
  const micBtn = $('micBtn');
  function micStatus(msg) { $('micStatus').hidden = !msg; $('micStatus').textContent = msg || ''; }

  async function startMic() {
    mic.base = box.value.trim(); mic.chunks = []; mic.live = ''; clearAudio();
    stopSpeaking();
    try {
      mic.stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 } });
      mic.ctx = new (window.AudioContext || window.webkitAudioContext)();
      const an = mic.ctx.createAnalyser(); an.fftSize = 1024; an.smoothingTimeConstant = 0.6;
      mic.ctx.createMediaStreamSource(mic.stream).connect(an);
      V.orb.setAnalyser(an);
      if (window.MediaRecorder) { mic.mr = new MediaRecorder(mic.stream); mic.mr.ondataavailable = e => { if (e.data.size) mic.chunks.push(e.data); }; mic.mr.start(); }
    } catch (_) { mic.stream = null; }
    mic.speech = V.speech.supported;
    if (mic.speech) {
      V.speech.onUpdate(t => { box.value = (mic.base ? mic.base + ' ' : '') + t; box.dispatchEvent(new Event('input')); });
      V.speech.start(opts.speechLang);
    } else if (!mic.stream) { toast('Microphone not available. Allow access in the browser, or type your answer.'); return false; }
    V.orb.setMode('listening');
    mic.on = true; micBtn.classList.add('rec'); micBtn.setAttribute('aria-pressed', true);
    micStatus(mic.speech ? 'Listening… speak, then tap the microphone again to stop. You can edit the text before sending.' : 'Recording… tap the microphone again to stop.');
    return true;
  }

  async function stopMic() {
    if (!mic.on) return;
    mic.on = false;
    let live = '';
    if (mic.speech) { live = await V.speech.stop(); box.value = (mic.base ? mic.base + ' ' : '') + live; box.dispatchEvent(new Event('input')); }
    mic.live = box.value;
    const blob = await new Promise(res => {
      if (mic.mr && mic.mr.state !== 'inactive') { mic.mr.onstop = () => res(new Blob(mic.chunks, { type: mic.mr.mimeType || 'audio/webm' })); mic.mr.stop(); }
      else res(null);
    });
    if (mic.stream) mic.stream.getTracks().forEach(t => t.stop());
    if (mic.ctx) mic.ctx.close();
    mic.stream = null; mic.ctx = null; mic.mr = null;
    V.orb.setAnalyser(null); V.orb.setMode('idle');
    micBtn.classList.remove('rec'); micBtn.setAttribute('aria-pressed', false); micStatus('');
    // Accurate mode, or a browser with no speech recognition: keep the recording so Gemini can transcribe it.
    if (blob && blob.size > 2000 && (opts.accurate || !mic.speech)) {
      try { state.pendingAudio = await V.wav.fromBlob(blob); showAudioChip(opts.accurate); }
      catch (_) { toast('Could not process the recording. Please check the text and send it, or type your answer.'); }
    }
  }
  micBtn.addEventListener('click', async () => { if (mic.on) await stopMic(); else await startMic(); });

  // ---- send one answer
  async function send({ timeout = false } = {}) {
    if (state.busy) return;
    if (mic.on) await stopMic();
    let text = box.value.trim();
    const audio = state.pendingAudio;
    const drawing = await V.whiteboard.toBlob();
    if (!text && !audio && !drawing) {
      if (!timeout) { toast('Write, speak or draw your answer first.'); return; }
      text = '[No answer: time ran out]';
    }
    stopTimer(); stopSpeaking();
    state.busy = true; setComposer(false);
    V.orb.setMode('thinking');
    const imgUrl = drawing ? URL.createObjectURL(drawing) : null;
    const shown = audio ? (text || '🎙 Voice answer') : text || '(whiteboard answer)';
    const mine = addBubble('me', shown, { imageUrl: imgUrl });
    const wait = typing();
    try {
      // With an attached recording the server transcribes it (more exact than the browser); otherwise the typed/live text is sent.
      const out = await V.api.answer(state.sessionId, { text: audio ? '' : text, audio, drawing });
      wait.remove();
      if (out.transcript && (audio || !text)) mine.querySelector('.body').textContent = out.transcript;
      if (out.drawing_description) {
        mine.querySelector('.bubble').insertAdjacentHTML('beforeend', '<span class="desc"></span>');
        mine.querySelector('.desc').textContent = 'The AI read your drawing as: ' + out.drawing_description;
      }
      box.value = ''; box.style.height = 'auto'; clearAudio(); V.whiteboard.clear();
      if (out.should_stop) {
        setDots(TOTAL + 1); V.orb.setMode('idle');
        $('thread').insertAdjacentHTML('beforeend', '<div class="sys-note">That was the last question. Marking your answers…</div>');
        $('thread').scrollTop = $('thread').scrollHeight;
        setTimeout(() => openReport(state.sessionId, $('chatTopic').textContent), 1400);
        return;
      }
      state.round = out.round; setDots(out.round);
      addBubble('ai', out.next_question, { label: 'Question ' + out.round, needsWhiteboard: out.needs_whiteboard, diagram: out.diagram_svg });
      presentQuestion({ text: out.next_question, needs_whiteboard: out.needs_whiteboard, diagram_svg: out.diagram_svg });
    } catch (err) {
      wait.remove(); mine.remove();
      toast(err.message);
      V.orb.setMode('idle');
      state.busy = false; setComposer(true);
      if (opts.timeLimit && !timeout) startTimer();
    }
  }

  $('exitChat').addEventListener('click', async () => {
    const answered = $('thread').querySelectorAll('.msg.me').length;
    if (mic.on) await stopMic();
    if (!answered) { await enterHome(); return; }
    if (!confirm('End the session now? You will get a report on what you have answered so far.')) return;
    try { await V.api.finish(state.sessionId); } catch (_) {}
    openReport(state.sessionId, $('chatTopic').textContent);
  });

  // ================================================================ report
  function metricCard(name, m) {
    const d = document.createElement('div'); d.className = 'metric';
    d.innerHTML = `<div class="metric-top"><b>${esc(name)}</b><span>${m.score}/10</span></div><div class="bar"><i></i></div><p>${esc(m.justification)}</p>`;
    requestAnimationFrame(() => requestAnimationFrame(() => d.querySelector('.bar i').style.width = (m.score * 10) + '%'));
    return d;
  }
  function selectTab(name) {
    document.querySelectorAll('.tab-card').forEach(t => t.classList.toggle('active', t.dataset.tab === name));
    ['gaps', 'fact', 'notes', 'transcript'].forEach(n => $('tab-' + n).hidden = n !== name);
  }
  document.querySelectorAll('.tab-card').forEach(t => t.addEventListener('click', () => selectTab(t.dataset.tab)));

  function skeleton() { return '<div class="skeleton"></div><div class="skeleton" style="width:80%"></div><div class="skeleton" style="width:60%"></div>'; }

  function setStatus(kind, html) {
    const el = $('reportStatus');
    el.hidden = !html; el.className = 'report-status ' + (kind || '');
    el.innerHTML = (kind === 'loading' ? '<div class="spinner"></div>' : '') + `<span>${html || ''}</span>`;
  }
  function setReportButtons(ready) {
    ['downloadBtn', 'fullDocBtn', 'mdBtn', 'retestBtn'].forEach(id => $(id).disabled = !ready);
    $('downloadBtn').textContent = ready ? 'Gap report (Word)' : 'Preparing report…';
  }

  /** A report built from the score alone (no AI call). Used when the AI cannot write the full one, so saving always works. */
  function basicReport(topic, score) {
    const names = ['accuracy', 'completeness', 'consistency', 'clarity'];
    const lines = ['# Mistake Report', '', '## Score Summary', `- Topic: ${topic || 'Session'}`, `- Overall: ${score.overall}/100`];
    names.forEach(n => lines.push(`- ${n[0].toUpperCase() + n.slice(1)}: ${score.scores[n].score}/10, ${score.scores[n].justification}`));
    lines.push('', '## Mistakes', '');
    let items = (score.mistakes || []).filter(Boolean);
    if (!items.length) {
      const weakest = names.slice().sort((a, b) => score.scores[a].score - score.scores[b].score)[0];
      items = [`Weakest area: ${weakest}. ${score.scores[weakest].justification}`];
    }
    items.forEach(m => lines.push('### Concept Misunderstood', m, '', '### Correct Explanation',
      'Compare this point with your study notes. (The AI could not write the full explanation this time.)', '',
      '### Recommended Review', 'Re-read this part of your notes, then explain it out loud again.', '', '---', ''));
    return lines.join('\n');
  }

  async function openReport(sessionId, topic) {
    state.sessionId = sessionId; state.reportMd = ''; state.reportBasic = false; state.score = null; state.notesMd = '';
    $('reportTopic').textContent = topic || '';
    $('reportLoading').innerHTML = LOADING_HTML;
    $('reportLoading').hidden = false; $('reportBody').hidden = true;
    setReportButtons(false); setStatus('', '');
    $('retrySame').style.display = state.upload ? '' : 'none';
    selectTab('gaps');
    show('report');
    let pkg;
    try { pkg = await V.api.result(sessionId, 'score', lang()); }
    catch (err) {
      $('reportLoading').innerHTML = `<p><strong>Could not mark this session.</strong><br><span class="muted">${esc(err.message)}</span></p><button class="btn ghost" id="retryScore">Try again</button>`;
      $('retryScore').addEventListener('click', () => openReport(sessionId, topic));
      return;
    }
    state.score = pkg.score;
    renderScore(pkg.score);
    $('reportLoading').hidden = true; $('reportBody').hidden = false;
    $('tab-gaps').innerHTML = skeleton(); $('tab-fact').innerHTML = skeleton(); $('tab-notes').innerHTML = skeleton();
    ['tcGaps', 'tcFact', 'tcNotes'].forEach(i => $(i).textContent = 'Preparing…');
    loadTranscript(sessionId);
    loadFull(sessionId);
  }
  const LOADING_HTML = $('reportLoading').innerHTML;

  function renderScore(score) {
    $('scoreNum').textContent = score.overall;
    requestAnimationFrame(() => requestAnimationFrame(() => $('scoreRing').style.setProperty('--pct', score.overall)));
    $('scoreSummary').textContent = score.summary;
    const mt = $('metrics'); mt.innerHTML = '';
    ['accuracy', 'completeness', 'consistency', 'clarity'].forEach(k => mt.appendChild(metricCard(k, score.scores[k])));
  }

  // ---- gap cards: open/close, tick off as reviewed (remembered per session)
  function reviewedKey() { return 'vocalis_reviewed_' + state.sessionId; }
  function getReviewed() { try { return JSON.parse(localStorage.getItem(reviewedKey()) || '[]'); } catch (_) { return []; } }
  function setReviewed(arr) { try { localStorage.setItem(reviewedKey(), JSON.stringify(arr)); } catch (_) {} }

  function renderGaps(markdown) {
    const panel = $('tab-gaps');
    panel.innerHTML = '<div class="gap-progress" hidden><span id="gapProgressText"></span><div class="bar"><i id="gapProgressBar"></i></div></div><div class="md">' + md(markdown) + '</div>';
    const cards = panel.querySelectorAll('.gap-card');
    const reviewed = new Set(getReviewed());
    const update = () => {
      const n = cards.length, done = panel.querySelectorAll('.gap-card.done').length;
      panel.querySelector('.gap-progress').hidden = !n;
      $('gapProgressText').textContent = `${done} of ${n} reviewed`;
      $('gapProgressBar').style.width = (n ? done / n * 100 : 0) + '%';
      setReviewed([...panel.querySelectorAll('.gap-card')].map((c, i) => c.classList.contains('done') ? i : -1).filter(i => i >= 0));
    };
    cards.forEach((card, i) => {
      const firstP = card.querySelector('p');
      const title = firstP ? firstP.textContent : 'Gap ' + (i + 1);
      const body = document.createElement('div'); body.className = 'gap-body';
      while (card.firstChild) body.appendChild(card.firstChild);
      const head = document.createElement('div'); head.className = 'gap-head';
      head.innerHTML = `<span class="gap-num">${i + 1}</span><span class="gap-title"></span><span class="gap-chev">▾</span>`;
      head.querySelector('.gap-title').textContent = title.length > 140 ? title.slice(0, 137) + '…' : title;
      const lab = document.createElement('label'); lab.className = 'check gap-check';
      lab.innerHTML = '<input type="checkbox"><span><b>I have reviewed this</b></span>';
      const cb = lab.querySelector('input');
      cb.addEventListener('change', () => { card.classList.toggle('done', cb.checked); update(); });
      body.appendChild(lab);
      card.append(head, body);
      head.addEventListener('click', () => card.classList.toggle('open'));
      if (reviewed.has(i)) { card.classList.add('done'); cb.checked = true; }
      if (i === 0) card.classList.add('open');
    });
    update();
    $('tcGaps').textContent = cards.length ? `${cards.length} to review` : 'Nothing major';
  }

  async function loadFull(sessionId) {
    setStatus('loading', 'Preparing your gap report, fact-check and notes… this uses a few AI requests.');
    let pkg = null, reason = '';
    try { pkg = await V.api.result(sessionId, 'full', lang()); }
    catch (err) { reason = err.message; }
    if (state.sessionId !== sessionId) return;

    // gap report: the AI one if there is one, otherwise a basic one built from the score so saving still works
    if (pkg && pkg.report_markdown) {
      state.reportMd = pkg.report_markdown; state.reportBasic = false;
      setStatus('ok', 'Your gap report is ready. Save it, or test yourself on it right away.');
    } else {
      reason = reason || (pkg && pkg.report_error) || 'the AI did not return a report';
      state.reportMd = basicReport($('reportTopic').textContent, state.score); state.reportBasic = true;
      setStatus('warn', `The AI could not write the full report (${esc(reason)}). A basic report built from your score is ready instead. <button class="btn ghost small" id="retryFull">Try the full report again</button>`);
      $('retryFull').addEventListener('click', () => { setReportButtons(false); loadFull(sessionId); });
    }
    renderGaps(state.reportMd);
    setReportButtons(true);

    // fact-check
    const fc = pkg && pkg.fact_check;
    if (fc && fc.findings) {
      const clear = /^no suspected errors/i.test(fc.findings.trim());
      $('tab-fact').innerHTML = `<div class="md">${md(fc.findings)}</div>` + (fc.sources && fc.sources.length
        ? '<h3 style="margin-top:20px">Sources</h3><ul class="sources">' + fc.sources.map(s => `<li><a href="${esc(s.url || s.uri || s)}" target="_blank" rel="noopener">${esc(s.title || s.url || s.uri || s)}</a></li>`).join('') + '</ul>' : '');
      $('tcFact').textContent = clear ? 'No issues found' : 'Issues to check';
    } else {
      $('tab-fact').innerHTML = `<p class="muted">Fact-check not available${(fc && fc.error) || reason ? ': ' + esc((fc && fc.error) || reason) : '.'}</p>`;
      $('tcFact').textContent = 'Not available';
    }

    // notes
    const n = pkg && pkg.notes;
    if (n && (n.notes || n.notes_translated)) {
      state.notesMd = n.notes + (n.notes_translated && n.language !== 'English' ? `\n\n---\n\n## ${n.language}\n\n${n.notes_translated}` : '');
      $('tab-notes').innerHTML = '<div class="panel-tools"><button class="btn ghost small" id="copyNotes">Copy notes</button><button class="btn ghost small" id="saveNotes">Download notes (.md)</button></div>' +
        `<div class="md">${md(n.notes)}</div>` + (n.notes_translated && n.language !== 'English' ? `<hr style="border:0;border-top:1px solid var(--line);margin:22px 0"><h3>${esc(n.language)}</h3><div class="md">${md(n.notes_translated)}</div>` : '');
      $('copyNotes').addEventListener('click', async () => { try { await navigator.clipboard.writeText(state.notesMd); toast('Notes copied.'); } catch (_) { toast('Could not copy. Select the text and copy it.'); } });
      $('saveNotes').addEventListener('click', () => download('revision-notes-' + sessionId + '.md', state.notesMd));
      $('tcNotes').textContent = n.language && n.language !== 'English' ? 'English + ' + n.language : 'English';
    } else {
      $('tab-notes').innerHTML = `<p class="muted">Notes not available${(n && n.error) || reason ? ': ' + esc((n && n.error) || reason) : '.'}</p>`;
      $('tcNotes').textContent = 'Not available';
    }
  }

  async function loadTranscript(sessionId) {
    const panel = $('tab-transcript'); panel.innerHTML = skeleton();
    try {
      const info = await V.api.session(sessionId);
      panel.innerHTML = '';
      let q = 0;
      for (const m of info.messages) {
        const line = document.createElement('div'); line.className = 't-line';
        const label = m.role === 'ai' ? 'Question ' + (++q) : 'You';
        const text = m.text.split('\n\n[Whiteboard drawing]\n');
        line.innerHTML = `<b>${label}</b><span></span>`;
        line.querySelector('span').textContent = text[0].replace(/^\[Whiteboard drawing\]\n/, '');
        if (m.diagram_svg) { const img = document.createElement('img'); img.src = svgUrl(m.diagram_svg); img.style.cssText = 'max-width:300px;border-radius:10px;margin-top:8px;display:block;background:#f1e7d0'; line.appendChild(img); }
        if (text[1] || m.text.startsWith('[Whiteboard drawing]')) {
          const d = document.createElement('div'); d.className = 'muted small'; d.style.fontStyle = 'italic';
          d.textContent = 'Whiteboard, as the AI read it: ' + (text[1] || text[0].replace('[Whiteboard drawing]\n', ''));
          line.appendChild(d);
        }
        if (m.has_drawing) {
          try { const img = document.createElement('img'); img.src = await V.api.drawingUrl(m.id); img.style.cssText = 'max-width:320px;border-radius:10px;margin-top:8px;display:block'; line.appendChild(img); } catch (_) {}
        }
        panel.appendChild(line);
      }
      $('tcConv').textContent = info.messages.length + ' messages';
    } catch (err) { panel.innerHTML = `<p class="muted">${esc(err.message)}</p>`; $('tcConv').textContent = 'Unavailable'; }
  }

  function download(name, content) {
    const blob = new Blob([content], { type: 'text/markdown' });
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  }
  function saveBlob(name, blob) {
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  }
  async function downloadDoc(kind, btn) {
    if (!state.sessionId) return;
    const old = btn.textContent; btn.disabled = true; btn.textContent = 'Creating Word file…';
    try {
      const blob = await V.api.exportDoc(state.sessionId, kind);
      saveBlob((kind === 'full' ? 'full-report-' : 'gap-report-') + state.sessionId + '.docx', blob);
      toast(kind === 'full' ? 'Full report saved to your Downloads folder.' : 'Gap report saved. Upload this file later to be tested on these gaps.');
    } catch (err) {
      toast(err.message);
      if (kind === 'gaps' && state.reportMd) download('gap-report-' + state.sessionId + '.md', state.reportMd);
    } finally { btn.disabled = false; btn.textContent = old; }
  }
  $('downloadBtn').addEventListener('click', () => downloadDoc('gaps', $('downloadBtn')));
  $('fullDocBtn').addEventListener('click', () => downloadDoc('full', $('fullDocBtn')));
  $('mdBtn').addEventListener('click', () => {
    if (!state.reportMd) return;
    download('gap-report-' + state.sessionId + '.md', state.reportMd);
    toast('Saved. Upload this file later to be tested on these gaps.');
  });
  $('retestBtn').addEventListener('click', async () => {
    if (!state.reportMd) return;
    const file = new File([state.reportMd], 'gap-report-' + state.sessionId + '.md', { type: 'text/markdown' });
    await handleUpload(file);
  });
  $('retrySame').addEventListener('click', () => state.upload && startSession(state.topic));
  $('goHome').addEventListener('click', enterHome);

  // ================================================================ boot
  async function showMode() {
    const b = $('modeBadge');
    try {
      const h = await V.api.health();
      b.className = 'mode-badge' + (h.fake_ai ? ' fake' : '');
      b.textContent = h.fake_ai ? 'Demo mode · no AI used' : (h.key_ending ? h.model : 'No API key');
      b.title = h.fake_ai ? 'Demo mode: canned questions and scores, no Gemini requests' : 'Gemini model in use: ' + h.model + (h.key_ending ? ' (key ending ' + h.key_ending + ')' : ' (no key found)');
      if (!h.fake_ai && !h.key_ending) b.classList.add('bad');
    } catch (_) { b.className = 'mode-badge bad'; b.textContent = 'Backend not reachable'; }
    b.hidden = false;
  }

  async function boot() {
    showMode();
    loadOpts(); paintOpts();
    try { const saved = localStorage.getItem('vocalis_lang'); if (saved) $('langSelect').value = saved; } catch (_) {}
    $('langSelect').addEventListener('change', () => { try { localStorage.setItem('vocalis_lang', lang()); } catch (_) {} });
    V.whiteboard.init({});
    setAuthMode('login');
    if (V.api.hasToken()) {
      try { state.user = await V.api.me(); await enterHome(); return; } catch (_) { /* token invalid: fall through to login */ }
    }
    show('auth');
  }
  boot();
})();
