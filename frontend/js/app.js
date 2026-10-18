/* Vocalis single-page app: login → home → topics → chat (AI asks, whiteboard when needed) → report. */
(() => {
  const V = window.Vocalis;
  const $ = id => document.getElementById(id);
  const SCREENS = ['auth', 'home', 'topics', 'chat', 'report', 'about', 'impact'];
  const TOTAL = 5;

  const state = {
    user: null, upload: null, topic: null, sessionId: null, round: 1, busy: false,
    pendingAudio: null, reportMd: '', reportBasic: false, authMode: 'login', score: null, mistakes: [], notesMd: ''
  };

  // ---------------------------------------------------------------- settings (remembered on this device)
  const opts = { timeLimit: 0, speechLang: 'en-IN', accurate: false, speak: false, voiceEngine: 'ai', aiVoice: 'Aoede', devVoice: '' };   // Aoede is the only voice offered
  function loadOpts() {
    try { Object.assign(opts, JSON.parse(localStorage.getItem('vocalis_opts') || '{}')); } catch (_) {}
    opts.voiceEngine = 'ai'; opts.aiVoice = 'Aoede'; opts.devVoice = '';
  }
  function saveOpts() { try { localStorage.setItem('vocalis_opts', JSON.stringify(opts)); } catch (_) {} }
  function paintOpts() {
    document.querySelectorAll('#timeChips .chip-btn').forEach(b => b.classList.toggle('active', +b.dataset.sec === opts.timeLimit));
    $('speechLang').value = opts.speechLang; $('optAccurate').checked = opts.accurate; $('optSpeak').checked = opts.speak;
    $('speakToggle').setAttribute('aria-pressed', opts.speak);
    $('voiceBox').style.display = opts.speak ? '' : 'none';
  }
  document.querySelectorAll('#timeChips .chip-btn').forEach(b => b.addEventListener('click', () => { opts.timeLimit = +b.dataset.sec; saveOpts(); paintOpts(); }));
  $('speechLang').addEventListener('change', e => { opts.speechLang = e.target.value; saveOpts(); });
  $('optAccurate').addEventListener('change', e => { opts.accurate = e.target.checked; saveOpts(); });
  $('optSpeak').addEventListener('change', e => { opts.speak = e.target.checked; saveOpts(); paintOpts(); });
  $('speakToggle').addEventListener('click', () => { opts.speak = !opts.speak; saveOpts(); paintOpts(); if (!opts.speak) stopSpeaking(); });

  // ---------------------------------------------------------------- voice
  // Aoede (Gemini text-to-speech) is the only voice. There is no device-voice stand-in.
  $('voicePreview').addEventListener('click', () => speakNow('Hello! I am Aoede. I will ask you five questions about your topic. Explain each one in your own words.', () => {}));

  // ---------------------------------------------------------------- helpers
  function show(name) {
    SCREENS.forEach(n => $('screen-' + n).hidden = n !== name);
    $('topbar').hidden = name === 'auth' || ((name === 'about' || name === 'impact') && !state.user);
    document.querySelectorAll('.nav-link').forEach(b => b.classList.toggle('active', b.dataset.nav === name || (b.dataset.nav === 'home' && ['topics', 'report'].includes(name))));
    V.orb.enable(name === 'chat');
    if (name !== 'chat') $('calcPanel').hidden = true;
    if (name === 'about') loadEvidence();
    if (name === 'impact') loadImpact();
    const badge = $('modeBadge');
    if (name === 'auth') { document.body.appendChild(badge); badge.classList.remove('in-topbar'); }
    else { $('topbarRight').prepend(badge); badge.classList.add('in-topbar'); }
    if (name !== 'chat') { stopChatWork(); }
    window.scrollTo(0, 0);
  }
  let toastTimer;
  function toast(msg) {
    if (msg === aiShown.msg && Date.now() - aiShown.at < 2000) return;      // the AI problem card already says it
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
    b.dataset.nav === 'about' ? show('about') : b.dataset.nav === 'impact' ? show('impact') : enterHome();
  }));
  $('aboutFromAuth').addEventListener('click', () => show('about'));
  $('impactFromAuth').addEventListener('click', () => show('impact'));
  $('impactBack').addEventListener('click', () => state.user ? enterHome() : show('auth'));
  $('aboutBack').addEventListener('click', () => state.user ? enterHome() : show('auth'));
  $('aboutStart').addEventListener('click', () => state.user ? enterHome() : show('auth'));
  $('brandLink').addEventListener('click', e => { e.preventDefault(); if (state.user && $('screen-chat').hidden) enterHome(); });

  // ================================================================ home
  async function enterHome() {
    $('userChip').textContent = state.user.name;
    $('userAvatar').textContent = (state.user.name.trim()[0] || '?').toUpperCase();
    $('homeTitle').textContent = 'Hello, ' + state.user.name.split(' ')[0] + '. What will you teach today?';
    $('uploadError').textContent = '';
    popOpen(false);
    show('home');
    loadHistory();
  }

  const popOpen = open => { $('profilePop').hidden = !open; $('userBtn').setAttribute('aria-expanded', open); if (open) loadProfile(); };
  $('userBtn').addEventListener('click', e => { e.stopPropagation(); popOpen($('profilePop').hidden); });
  document.addEventListener('click', e => { if (!$('profileMenu').contains(e.target)) popOpen(false); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') popOpen(false); });

  async function loadProfile() {
    const box = $('profileBox');
    try {
      const p = await V.api.profile();
      const tiers = [['platinum', '💎'], ['gold', '🥇'], ['silver', '🥈'], ['bronze', '🥉']];
      box.innerHTML = '<div class="tier-row">' + tiers.map(([t, i]) => `<div class="tier ${p.tiers[t] ? 'on' : ''}"><span>${i}</span><b>${p.tiers[t]}</b><small>${t}</small></div>`).join('') + '</div>' +
        '<div class="special-row">' + p.specials.map(s => `<span class="special ${s.earned ? 'on' : ''}" title="${esc(s.desc)}">${s.icon} ${esc(s.name)}</span>`).join('') + '</div>' +
        `<p class="muted small">${p.clean} honest session(s)${p.average != null ? ' · average ' + p.average : ''}${p.flagged ? ' · ' + p.flagged + ' flagged (no badge)' : ''}. Badges: 40+ bronze, 60+ silver, 80+ gold, 90+ platinum.</p>`;
    } catch (_) { box.innerHTML = ''; }
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
          (s.overall != null ? `<span class="pill ${s.badge ? s.badge.tier : ''}" title="${s.badge ? esc(s.badge.name) : ''}">${s.badge ? s.badge.icon + ' ' : ''}${s.overall}</span>` : `<span class="pill live">${s.status === 'active' ? 'Continue' : 'View'}</span>`);
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
    if (needKey()) return;
    $('uploadError').textContent = '';
    drop.classList.add('busy');
    $('dropTitle').textContent = 'Reading ' + file.name + '…';
    try {
      state.upload = await V.api.uploadFile(file);
      renderTopics();
    } catch (err) {
      setResume(err, () => handleUpload(file));
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
    const sel = $('topicSelect'); sel.innerHTML = '';
    const clean = t => t.replace(/^\s*(\d+(\.\d+)*[.)]|[IVXLC]+\.)\s+/, '');
    u.sections.forEach((sec, i) => {
      const o = document.createElement('option'); o.value = String(i); o.textContent = `${i + 1}. ${clean(sec.title)}`; sel.appendChild(o);
    });
    if (u.sections.length > 1) { const o = document.createElement('option'); o.value = 'all'; o.textContent = 'Whole document'; sel.appendChild(o); }
    show('topics');
  }
  $('topicsBack').addEventListener('click', enterHome);
  // ---- big confidence sliders: face, number and a sentence change as you drag
  const FACES = ['😟', '😟', '😕', '😕', '🤔', '😐', '🙂', '🙂', '😀', '😄', '😎'];
  const CONF_TEXT = ['Lost: I would not know where to start.', 'Very unsure.', 'Mostly unsure.', 'A little shaky.', 'Some bits, not all.', 'Halfway there.', 'Fairly comfortable.', 'Quite good.', 'Confident.', 'Very confident.', 'I could teach this to anyone.'];
  function bindConf(sliderId, faceId, valId, textId) {
    const sl = $(sliderId);
    const paint = () => {
      const v = +sl.value;
      $(faceId).textContent = FACES[v]; $(valId).textContent = v;
      if (textId) $(textId).textContent = CONF_TEXT[v];
      sl.style.setProperty('--pct', (v * 10) + '%');
    };
    sl.addEventListener('input', () => { paint(); if (sliderId === 'confAfter') paintCalib(); });
    paint(); return paint;
  }
  const paintConfBefore = bindConf('confSlider', 'confFace', 'confVal', 'confText');
  $('topicStart').addEventListener('click', async () => {
    const v = $('topicSelect').value, b = $('topicStart'); b.disabled = true;
    try { await startSession(v === 'all' ? null : state.upload.sections[+v].title); } finally { b.disabled = false; }
  });

  async function startSession(topic) {
    if (needKey()) return;
    $('startError').textContent = '';
    try {
      const s = await V.api.start(state.upload.upload_id, topic, opts.timeLimit, +$('confSlider').value);
      state.topic = topic;
      openChat(s.session_id, s.topic, s.round, [{ role: 'ai', text: s.next_question, needs_whiteboard: s.needs_whiteboard, diagram_svg: s.diagram_svg }]);
    } catch (err) {
      setResume(err, () => startSession(topic));
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
  // Only one thing may be "in the air" at a time: the voice request, the audio, the answer request. All of it can be cancelled.
  let voiceAudio = null, ttsCtl = null, readToken = 0, inflight = null;
  const SKIP_AFTER_MS = 20000;                  // if Aoede is still not ready after this long, a Skip button appears (there is no time limit on Aoede itself)
  let speakGen = 0;                             // bumped whenever the reading is cancelled, so late callbacks know to do nothing
  function stopSpeaking() {
    speakGen++;
    try { window.speechSynthesis && window.speechSynthesis.cancel(); } catch (_) {}
    if (ttsCtl) { try { ttsCtl.abort(); } catch (_) {} ttsCtl = null; }
    if (voiceAudio) { try { voiceAudio.pause(); } catch (_) {} voiceAudio = null; }
  }
  /** Cancel everything the chat is doing in the background: reading aloud, timer, and a pending answer/next-question request. */
  function stopChatWork() {
    readToken++;                                // a late "reading finished" callback must not start a timer or unlock the box
    stopSpeaking(); stopTimer();
    if (inflight) { try { inflight.abort(); } catch (_) {} inflight = null; }
    $('readStatus').hidden = true; clearTimeout(skipTimer);
  }
  // Aoede is the only voice. There is no time limit on it and no other voice stands in for it.
  async function speakNow(text, done) {
    stopSpeaking();
    const gen = speakGen;
    const ctl = new AbortController(); ttsCtl = ctl;
    try {
      const url = await V.api.tts(text, opts.aiVoice, ctl.signal);
      if (gen !== speakGen) return;                                  // the chat moved on while the voice was loading
      ttsCtl = null;
      const a = new Audio(url); voiceAudio = a; a.playbackRate = 1.1;      // same delivery as before
      let finished = false;
      const end = () => { if (finished) return; finished = true; V.orb.setMode('idle'); voiceAudio = null; done(); };
      a.onended = end; a.onerror = end;
      V.orb.setMode('speaking');
      $('readText').textContent = '🔊 Aoede is reading the question. You can answer when she finishes.';
      await a.play();
    } catch (err) {
      if (gen !== speakGen) return;                                  // cancelled on purpose (left the chat, skipped, next question)
      ttsCtl = null; voiceAudio = null; V.orb.setMode('idle');
      toast('Aoede could not read this question (' + ((err && err.message) || 'unavailable') + '). Read it on screen and answer when you are ready.');
      done();
    }
  }
  function speak(text, done) {
    if (!opts.speak) { done(); return; }
    speakNow(text, done);
  }
  // With read-aloud on, the answer box stays locked until Aoede has finished the question. Then the box opens and the countdown
  // (if there is a time limit) appears at the same moment, so nobody gets extra or less time because of the reading.
  let began = -1, skipTimer = null;
  function beginAnswering(token) {
    if (token !== readToken || began === token) return;
    began = token; clearTimeout(skipTimer);
    $('readStatus').hidden = true;
    setComposer(true); $('answerBox').focus();
    startTimer();
  }
  $('readSkip').addEventListener('click', () => { const t = readToken; stopSpeaking(); V.orb.setMode('idle'); beginAnswering(t); });

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
    state.busy = false;
    stopSpeaking(); stopTimer();
    const token = ++readToken;
    if (!opts.speak) { setComposer(true); $('answerBox').focus(); beginAnswering(token); return; }      // nothing to read: the box opens at once
    setComposer(false);
    $('readText').textContent = '🔊 Aoede is getting ready to read the question. You can answer when she finishes.';
    $('readSkip').hidden = true; $('readStatus').hidden = false;
    clearTimeout(skipTimer); skipTimer = setTimeout(() => { if (token === readToken && began !== token) $('readSkip').hidden = false; }, SKIP_AFTER_MS);
    speak(q.text, () => beginAnswering(token));
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
    ['answerBox', 'sendBtn', 'micBtn', 'wbToggle', 'calcToggle'].forEach(i => $(i).disabled = !enabled);
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
  // ---- honesty checks: paste is blocked and counted, leaving the page is counted (both are reported with the next answer)
  const guard = { paste: 0, tabs: 0 };
  ['paste', 'drop'].forEach(ev => box.addEventListener(ev, e => {
    e.preventDefault(); guard.paste++;
    toast('Pasting is turned off. Explain it in your own words. This is recorded.');
  }));
  document.addEventListener('visibilitychange', () => {
    if (document.hidden && visible('chat') && !state.busy) guard.tabs++;
  });
  function visible(name) { const el = $('screen-' + name); return !!el && !el.hidden; }

  // ---- calculator (like the whiteboard: open it, use it, the answer stays yours to write)
  const calcUi = V.calc.mount($('calcPanel'));
  const setCalc = open => { $('calcPanel').hidden = !open; $('calcToggle').setAttribute('aria-pressed', open); if (open) $('calcInput').focus(); };
  $('calcToggle').addEventListener('click', () => setCalc($('calcPanel').hidden));
  $('calcClose').addEventListener('click', () => setCalc(false));
  $('calcUse').addEventListener('click', () => calcUi.insertInto(box));

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
    stopTimer(); stopSpeaking(); $('readStatus').hidden = true;
    state.busy = true; setComposer(false);
    V.orb.setMode('thinking');
    const imgUrl = drawing ? URL.createObjectURL(drawing) : null;
    const shown = audio ? (text || '🎙 Voice answer') : text || '(whiteboard answer)';
    const mine = addBubble('me', shown, { imageUrl: imgUrl });
    const wait = typing();
    try {
      // With an attached recording the server transcribes it (more exact than the browser); otherwise the typed/live text is sent.
      const ctl = new AbortController(); inflight = ctl;
      const out = await V.api.answer(state.sessionId, { text: audio ? '' : text, audio, drawing, integrity: { paste: guard.paste, tabs: guard.tabs } }, ctl.signal);
      if (inflight === ctl) inflight = null;
      guard.paste = 0; guard.tabs = 0;
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
      inflight = null;
      if (err && err.name === 'AbortError') { wait.remove(); state.busy = false; return; }      // the student ended the session: the report takes over
      setResume(err, () => send({ timeout }));      // the typed text, recording and drawing are still in place, so sending again is enough
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
    stopChatWork();                                   // stop the voice, the timer and any question the AI is still writing
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
    ['gaps', 'notes', 'transcript'].forEach(n => $('tab-' + n).hidden = n !== name);
  }
  document.querySelectorAll('.tab-card').forEach(t => t.addEventListener('click', () => selectTab(t.dataset.tab)));

  function skeleton() { return '<div class="skeleton"></div><div class="skeleton" style="width:80%"></div><div class="skeleton" style="width:60%"></div>'; }

  function setStatus(kind, html) {
    const el = $('reportStatus');
    el.hidden = !html; el.className = 'report-status ' + (kind || '');
    el.innerHTML = (kind === 'loading' ? '<div class="spinner"></div>' : '') + `<span>${html || ''}</span>`;
  }
  function setReportButtons(ready) {
    ['downloadBtn', 'fullDocBtn', 'retestBtn'].forEach(id => $(id).disabled = !ready);
    $('downloadBtn').textContent = ready ? 'Gap report (Word)' : 'Preparing report…';
    $('fullDocBtn').textContent = ready ? 'Revision notes (Word)' : 'Preparing…';
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
    state.sessionId = sessionId; state.reportMd = ''; state.reportBasic = false; state.score = null; state.notesMd = ''; feedbackNeeded = false;
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
      setResume(err, () => openReport(sessionId, topic));
      $('reportLoading').innerHTML = `<p><strong>Could not mark this session.</strong><br><span class="muted">${esc(err.message)}</span></p><button class="btn ghost" id="retryScore">Try again</button>`;
      $('retryScore').addEventListener('click', () => openReport(sessionId, topic));
      return;
    }
    state.score = pkg.score;
    renderScore(pkg.score);
    renderIntegrity(pkg);
    renderFeedback(sessionId, pkg);
    $('reportLoading').hidden = true; $('reportBody').hidden = false;
    $('tab-gaps').innerHTML = skeleton(); $('tab-notes').innerHTML = skeleton();
    ['tcGaps', 'tcNotes'].forEach(i => $(i).textContent = 'Preparing…');
    loadTranscript(sessionId);
    loadFull(sessionId);
  }
  const LOADING_HTML = $('reportLoading').innerHTML;

  // ---- confidence before the test vs the real score, and the feedback form (stored locally, no AI request)
  let stars = 0, picked = new Set(), calibState = null;
  const STAR_TEXT = ['', 'Not useful', 'A little useful', 'Useful', 'Very useful', 'Extremely useful'];
  const TAGS = ['Questions were good', 'Questions too hard', 'Questions too easy', 'Found gaps I missed', 'Diagram helped', 'Whiteboard helped', 'Calculator helped', 'Voice worked well', 'Report was clear', 'Too slow', 'Not accurate enough', 'Want this for my subjects'];
  const paintAfter = bindConf('confAfter', 'afterFace', 'confAfterVal', null);

  function paintCalib() {
    const box = $('calibBars');
    if (!calibState) { box.innerHTML = ''; return; }
    const rows = [];
    if (calibState.before != null) rows.push(['You predicted', calibState.before, 'b1']);
    rows.push(['You scored', calibState.actual, 'b2']);
    rows.push(['You feel now', +$('confAfter').value * 10, 'b3']);
    box.innerHTML = rows.map(([l, v, c]) => `<div class="cb"><span>${l}</span><div class="cb-track"><i class="${c}" style="width:${v}%"></i></div><b>${v}</b></div>`).join('');
  }

  function renderFeedback(sessionId, pkg) {
    const cal = $('calibration'), actual = pkg.score.overall;
    calibState = { before: pkg.confidence != null ? pkg.confidence * 10 : null, actual };
    if (pkg.confidence != null) {
      const gap = calibState.before - actual;
      cal.textContent = `You predicted ${calibState.before}/100 and scored ${actual}/100. ` + (gap >= 15 ? 'You were more confident than your explanation showed. That is exactly the gap this tool is for.' : gap <= -15 ? 'You knew more than you thought.' : 'Your self-assessment was close.');
    } else cal.textContent = '';
    const done = !!pkg.feedback; stars = done ? pkg.feedback.useful : 0; picked = new Set(done ? pkg.feedback.tags || [] : []);
    recommend = done ? pkg.feedback.recommend || '' : '';
    afterTouched = done && pkg.feedback.confidence_after != null;
    feedbackNeeded = !done;
    setFeedbackState(done);
    const save = async (quiet) => {
      if (!stars) { toast('Tap a star to rate how useful it was.'); return false; }
      const body = { useful: stars, comment: $('fbComment').value, tags: [...picked], recommend };
      if (afterTouched) body.confidence_after = +$('confAfter').value;
      try {
        await V.api.feedback(sessionId, body);
        feedbackNeeded = false; setFeedbackState(true);
        if (!quiet) toast('Thank you. Feedback saved.');
        return true;
      } catch (e) { toast(e.message); return false; }
    };
    // The five buttons are created ONCE. (Rebuilding them on hover removed the button under the mouse between press and release, so a mouse click never registered.)
    $('stars').innerHTML = [1, 2, 3, 4, 5].map(i => `<button type="button" class="star" data-n="${i}" role="radio" aria-label="${i} of 5: ${STAR_TEXT[i]}">★</button>`).join('');
    const starBtns = [...$('stars').querySelectorAll('.star')];
    const paintStars = (hover = 0) => {
      const n = hover || stars;
      starBtns.forEach((b, k) => { b.classList.toggle('on', k < n); b.setAttribute('aria-checked', String(k + 1 === stars)); });
      $('starLabel').textContent = n ? STAR_TEXT[n] : 'Tap a star';
    };
    starBtns.forEach(b => {
      b.addEventListener('click', () => { stars = +b.dataset.n; paintStars(); save(true); });      // one tap saves the rating
      b.addEventListener('mouseenter', () => paintStars(+b.dataset.n));
    });
    $('stars').onmouseleave = () => paintStars();
    paintStars();
    const paintRec = () => $('recRow').querySelectorAll('.rec').forEach(b => b.classList.toggle('on', b.dataset.v === recommend));
    $('recRow').querySelectorAll('.rec').forEach(b => b.onclick = () => { recommend = recommend === b.dataset.v ? '' : b.dataset.v; paintRec(); if (stars) save(true); });
    paintRec();
    $('fbTags').innerHTML = TAGS.map(t => `<button type="button" class="fb-tag ${picked.has(t) ? 'on' : ''}">${esc(t)}</button>`).join('');
    $('fbTags').querySelectorAll('.fb-tag').forEach(b => b.addEventListener('click', () => { const t = b.textContent; picked.has(t) ? picked.delete(t) : picked.add(t); b.classList.toggle('on'); }));
    $('confAfter').value = done && pkg.feedback.confidence_after != null ? pkg.feedback.confidence_after : 5; paintAfter();
    $('confAfter').oninput = () => { afterTouched = true; };
    $('fbComment').value = done ? pkg.feedback.comment || '' : '';
    paintCalib();
    $('fbSend').onclick = () => save(false);
  }

  // ---- feedback is required: leaving the report waits for one tap on the stars
  let recommend = '', afterTouched = false, feedbackNeeded = false;
  function setFeedbackState(done) {
    $('fbDone').hidden = !done; $('reqTag').hidden = done; $('fbNeed').hidden = done;
    $('feedbackCard').classList.toggle('is-done', done);
    $('fbSend').textContent = done ? 'Saved ✓ Update feedback' : 'Send feedback';
  }
  function nudgeFeedback() {
    const c = $('feedbackCard');
    if (c.scrollIntoView) c.scrollIntoView({ behavior: 'smooth', block: 'center' });
    c.classList.remove('nudge'); void c.offsetWidth; c.classList.add('nudge');
    toast('One quick step first: tap a star for how useful this session was.');
  }
  document.addEventListener('click', e => {
    if (!feedbackNeeded || $('screen-report').hidden) return;
    if (!e.target.closest('.nav-link, #goHome, #retrySame, #retestBtn, #downloadBtn, #fullDocBtn, #brandLink, #logoutBtn')) return;
    e.preventDefault(); e.stopImmediatePropagation(); nudgeFeedback();
  }, true);


  // ================================================================ impact page: charts built from the anonymous totals
  const pctOf = (n, d) => d ? Math.round(n / d * 100) : 0;
  const vbars = (vals, labels, cls = '') => { const mx = Math.max(1, ...vals); return '<div class="vbars ' + cls + '">' + vals.map((v, i) => `<div class="vb"><span class="vb-n">${v}</span><i style="height:${Math.max(v ? 4 : 0, v / mx * 100)}%"></i><small>${esc(labels[i])}</small></div>`).join('') + '</div>'; };
  const hbars = (rows, max, unit = '') => rows.map(([l, v, c]) => `<div class="hb"><span>${esc(l)}</span><div class="hb-track"><i class="${c || ''}" style="width:${max ? Math.min(100, v / max * 100) : 0}%"></i></div><b>${v == null ? '–' : v}${v == null ? '' : unit}</b></div>`).join('');
  const chartCard = (title, why, inner, wide) => `<div class="card chart${wide ? ' wide' : ''}"><h3>${esc(title)}</h3><p class="muted small">${esc(why)}</p>${inner}</div>`;
  const tile = (n, label) => `<div class="tile"><b>${n}</b><span>${esc(label)}</span></div>`;

  function renderImpact(d) {
    if (!d.sessions) return '<div class="card"><p class="muted">No independent finished sessions yet' + (d.flagged ? ` (${d.flagged} flagged session${d.flagged === 1 ? ' is' : 's are'} left out)` : '') + '. Finish one session and rate it, and the charts appear here.</p></div>';
    const c = d.confidence, r = d.retry, rec = d.recommend, recTotal = rec.yes + rec.maybe + rec.no;
    const tiles = [
      tile(d.students, 'students'), tile(d.sessions, 'honest sessions'), tile(d.average_score ?? '–', 'average score / 100'),
      tile(d.average_usefulness != null ? d.average_usefulness + ' / 5' : '–', `usefulness (${d.ratings} rating${d.ratings === 1 ? '' : 's'})`),
      tile(r.topics ? `${r.improved} of ${r.topics}` : '–', 'retried topics that improved'),
      tile(c.rated ? pctOf(c.overconfident, c.rated) + '%' : '–', 'felt more sure than they scored'),
    ].join('');
    const hist = chartCard('How scores are spread', 'Each bar counts sessions in a band of ten points. It shows whether the questions are neither too easy nor too hard.',
      vbars(d.score_histogram, d.score_histogram.map((_, i) => (i * 10) + (i === 9 ? '+' : '')), 'score'));
    const crit = chartCard('Where students are weakest', 'Average mark out of 10 for each thing the examiner AI scores. The lowest bar is where teaching should focus.',
      hbars(Object.entries(d.criteria_average).map(([k, v]) => [k[0].toUpperCase() + k.slice(1), v, '']), 10, ' /10'));
    const useful = chartCard('How useful students found it', 'Stars from the feedback form. Rating it is required, so these are not only the happy ones.',
      vbars(d.usefulness_counts, ['1★', '2★', '3★', '4★', '5★']) +
      (recTotal ? `<p class="small" style="margin-top:12px"><b>Would recommend to a classmate:</b> ${pctOf(rec.yes, recTotal)}% yes · ${pctOf(rec.maybe, recTotal)}% maybe · ${pctOf(rec.no, recTotal)}% no (${recTotal} answers)</p>` : ''));
    const conf = chartCard('Do students know what they know?', 'Average confidence before the test, the real score, and confidence after. A gap between the first two is the illusion of knowing that explaining out loud exposes.',
      c.rated ? hbars([['Predicted before', c.average_before, 'b1'], ['Actually scored', c.average_actual, 'b2'], ['Felt after', c.average_after, 'b3']], 100, '%') +
        `<p class="small" style="margin-top:12px">${c.overconfident} more sure than they scored · ${c.close} close · ${c.underconfident} knew more than they thought (out of ${c.rated})</p>` : '<p class="muted">No confidence ratings yet.</p>');
    const retry = chartCard('Did retrying help?', 'Each row is one topic a student tried again: the dot on the left is the first score, the dot on the right is the latest.',
      r.pairs.length ? `<div class="dumb">${r.pairs.map(p => { const lo = Math.min(p.first, p.last), hi = Math.max(p.first, p.last); return `<div class="dumb-row"><div class="dumb-track"><i class="dumb-line ${p.last >= p.first ? 'up' : 'down'}" style="left:${lo}%;width:${Math.max(1, hi - lo)}%"></i><u class="d1" style="left:${p.first}%"></u><u class="d2" style="left:${p.last}%"></u></div><b>${p.last - p.first >= 0 ? '+' : ''}${p.last - p.first}</b></div>`; }).join('')}</div>` +
        `<p class="small" style="margin-top:10px">Average change <b>${r.average_gain >= 0 ? '+' : ''}${r.average_gain}</b> points across ${r.topics} retried topic${r.topics === 1 ? '' : 's'}.</p>` : '<p class="muted">No retries yet.</p>', true);
    const tagMax = d.tags.length ? d.tags[0][1] : 0;
    const tags = chartCard('What students said stood out', 'Options they tapped on the feedback form.', d.tags.length ? hbars(d.tags.map(([t, n]) => [t, n, '']), tagMax) : '<p class="muted">No tags yet.</p>');
    const bd = Object.entries(d.badges).sort((a, b) => b[1] - a[1]);
    const badges = chartCard('Badges earned', 'Counted from the overall score. Flagged sessions earn none.', bd.length ? hbars(bd.map(([n, v]) => [n, v, n === 'Flagged' ? 'bad' : '']), bd[0][1]) : '<p class="muted">None yet.</p>');
    const integ = chartCard('Honest practice', 'Sessions where paste, tab switching or copying from the notes was detected are flagged and left out of the charts above.',
      hbars([['Independent', d.sessions, ''], ['Flagged', d.flagged, 'bad']], Math.max(d.sessions, d.flagged, 1)) + `<p class="small" style="margin-top:10px">${d.started} session${d.started === 1 ? '' : 's'} started in total · ${d.timed_sessions} used a time limit.</p>`);
    const hourly = d.bucket === 'hour';
    const lbl = iso => hourly ? new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : new Date(iso).toLocaleDateString([], { day: 'numeric', month: 'short' });
    const days = chartCard(hourly ? 'Sessions per hour' : 'Sessions per day', hourly ? 'Finished sessions by the hour inside the chosen window (your local time).' : 'Finished sessions per day.', d.per_bucket.length ? vbars(d.per_bucket.map(x => x[1]), d.per_bucket.map(x => lbl(x[0]))) : '<p class="muted">No sessions in this window.</p>');
    return `<div class="tiles">${tiles}</div><div class="chart-grid">${hist}${crit}${useful}${conf}${retry}${tags}${badges}${integ}${days}</div>`;
  }
  // ---- time window: add up only a period (last 3 hours, today, an exact range)
  const win = { hours: 0, since: '', until: '' };
  const winQuery = () => win.since || win.until ? '?' + [win.since && 'since=' + encodeURIComponent(win.since), win.until && 'until=' + encodeURIComponent(win.until)].filter(Boolean).join('&') : win.hours ? '?hours=' + win.hours : '';
  const fmtLocal = iso => new Date(iso).toLocaleString([], { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
  function winText() {
    if (win.since || win.until) return (win.since ? 'from ' + fmtLocal(win.since) : 'from the start') + (win.until ? ' to ' + fmtLocal(win.until) : ' until now');
    return win.hours ? (win.hours === 1 ? 'the last hour' : 'the last ' + win.hours + ' hours') : 'all time';
  }
  document.querySelectorAll('#winChips .chip-btn').forEach(b => b.addEventListener('click', () => {
    win.hours = +b.dataset.h; win.since = win.until = ''; $('winFrom').value = $('winTo').value = '';
    document.querySelectorAll('#winChips .chip-btn').forEach(x => x.classList.toggle('active', x === b));
    loadImpact();
  }));
  $('winApply').addEventListener('click', () => {
    const a = $('winFrom').value, z = $('winTo').value;
    if (!a && !z) { toast('Pick a start time, an end time, or both.'); return; }
    win.hours = 0; win.since = a ? new Date(a).toISOString() : ''; win.until = z ? new Date(z).toISOString() : '';
    document.querySelectorAll('#winChips .chip-btn').forEach(x => x.classList.remove('active'));
    loadImpact();
  });
  async function loadImpact() {
    const box = $('impactBody'); box.innerHTML = '<p class="muted">Loading…</p>';
    $('winLabel').innerHTML = '<b>Showing:</b> ' + esc(winText());
    try { const d = await V.api.insights(winQuery()); box.innerHTML = renderImpact(d); $('winLabel').innerHTML = '<b>Showing:</b> ' + esc(winText()) + ` · ${d.sessions} independent session${d.sessions === 1 ? '' : 's'}, ${d.flagged} flagged`; }
    catch (e) { box.innerHTML = '<div class="card"><p class="muted">Could not load the numbers: ' + esc(e.message) + '</p></div>'; }
  }
  $('fbCsv').addEventListener('click', () => {
    const k = $('fbKey').value.trim();
    const q = winQuery();
    window.open('/feedback/export.csv' + (k ? (q ? q + '&' : '?') + 'key=' + encodeURIComponent(k) : q), '_blank');
  });
  if (location.hash === '#impact') setTimeout(() => { if (!state.user) show('impact'); }, 300);

  async function loadEvidence() {
    try {
      const s = await V.api.stats();
      if (!s.sessions) return;
      const bits = [`${s.students} student(s), ${s.sessions} honest session(s), average score ${s.average_score}`];
      if (s.retried_topics) bits.push(`${s.improved_on_retry} of ${s.retried_topics} retried topics improved (average ${s.average_gain_on_retry >= 0 ? '+' : ''}${s.average_gain_on_retry} points)`);
      if (s.confidence_rated) bits.push(`${s.overconfident} of ${s.confidence_rated} students rated their confidence at least 15 points above their real score`);
      if (s.feedback_count) bits.push(`average usefulness ${s.average_usefulness} / 5 from ${s.feedback_count} rating(s)`);
      let extra = '';
      try {
        const f = await V.api.feedbackSummary();
        if (f.tags && f.tags.length) extra = '<p style="margin-top:10px"><b>What students tapped:</b> ' + f.tags.slice(0, 8).map(([t, n]) => esc(t) + ' (' + n + ')').join(' · ') + '</p>';
        if (f.average_confidence_before_pct != null && f.average_confidence_after_pct != null) bits.push(`average confidence before ${f.average_confidence_before_pct}%, after ${f.average_confidence_after_pct}%`);
      } catch (_) {}
      $('evidence').innerHTML = '<ul>' + bits.map(b => '<li>' + esc(b) + '</li>').join('') + '</ul>' + extra;
      $('evidenceCard').hidden = false;
    } catch (_) {}
  }

  function renderIntegrity(pkg) {
    const chip = $('reportBadge'), bn = $('integrityBanner'), b = pkg.badge, iv = pkg.integrity || {};
    chip.hidden = !b; if (b) { chip.textContent = b.icon + ' ' + b.name; chip.className = 'badge-chip ' + b.tier; }
    bn.hidden = !iv.flagged;
    if (iv.flagged) bn.innerHTML = '<b>⚠ This session is marked as not independent work, so it earns no badge.</b><ul>' + iv.reasons.map(r => '<li>' + esc(r) + '</li>').join('') + '</ul>';
  }

  function renderScore(score) {
    $('scoreNum').textContent = score.overall;
    requestAnimationFrame(() => requestAnimationFrame(() => $('scoreRing').style.setProperty('--pct', score.overall)));
    $('scoreSummary').textContent = score.summary;
    const mt = $('metrics'); mt.innerHTML = '';
    ['accuracy', 'completeness', 'consistency', 'clarity'].forEach(k => mt.appendChild(metricCard(k, score.scores[k])));
  }

  // ---- progress across attempts at the same topic (stored scores only, no AI request)
  async function renderProgress(sessionId) {
    const card = $('progressCard'); card.hidden = true;
    let att = [];
    try { att = (await V.api.progress(sessionId)).attempts; } catch (_) { return; }
    if (state.sessionId !== sessionId) return;
    card.hidden = false;
    if (att.length < 2) { card.innerHTML = '<h3>Your progress</h3><p class="muted">This is your first attempt at this topic. Study your gaps, then use “Try this topic again” to see your improvement here.</p>'; return; }
    const W = 640, H = 220, L = 40, R = 20, T = 20, B = 36;
    const x = i => L + (W - L - R) * (att.length === 1 ? 0.5 : i / (att.length - 1));
    const y = v => T + (H - T - B) * (1 - v / 100);
    const pts = att.map((a, i) => `${x(i)},${y(a.overall)}`).join(' ');
    let svg = `<svg viewBox="0 0 ${W} ${H}" class="prog-svg" role="img" aria-label="Score for each attempt">`;
    [0, 50, 100].forEach(g => { svg += `<line x1="${L}" x2="${W - R}" y1="${y(g)}" y2="${y(g)}" class="grid"/><text x="${L - 8}" y="${y(g) + 4}" text-anchor="end">${g}</text>`; });
    svg += `<polyline points="${pts}" class="line"/>`;
    att.forEach((a, i) => { svg += `<circle cx="${x(i)}" cy="${y(a.overall)}" r="5" class="dot${i === att.length - 1 ? ' last' : ''}"/><text x="${x(i)}" y="${y(a.overall) - 11}" text-anchor="middle" class="val">${a.overall}</text><text x="${x(i)}" y="${H - 12}" text-anchor="middle">Try ${i + 1}</text>`; });
    svg += '</svg>';
    const first = att[0], last = att[att.length - 1], d = last.overall - first.overall;
    const rows = ['accuracy', 'completeness', 'consistency', 'clarity'].map(k => {
      const dv = (last.scores[k] || 0) - (first.scores[k] || 0);
      return `<div class="crit"><span>${k[0].toUpperCase() + k.slice(1)}</span><div class="crit-bars"><i class="b1" style="width:${(first.scores[k] || 0) * 10}%"></i><i class="b2" style="width:${(last.scores[k] || 0) * 10}%"></i></div><b class="${dv > 0 ? 'up' : dv < 0 ? 'down' : ''}">${dv > 0 ? '+' : ''}${dv}</b></div>`;
    }).join('');
    card.innerHTML = `<h3>Your progress on this topic</h3><p class="prog-head ${d >= 0 ? 'up' : 'down'}">${first.overall} → ${last.overall} <span>(${d >= 0 ? '+' : ''}${d} points over ${att.length} attempts)</span></p>${svg}<p class="muted small legend"><i class="b1"></i> first attempt <i class="b2"></i> latest attempt, out of 10 per criterion</p>${rows}`;
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
    setStatus('loading', 'Preparing your gap report and revision notes… this uses a couple of AI requests.');
    let pkg = null, reason = '';
    try { pkg = await V.api.result(sessionId, 'full', lang()); }
    catch (err) { reason = err.message; setResume(err, () => loadFull(sessionId)); }
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
    renderProgress(sessionId);

    // notes
    const n = pkg && pkg.notes;
    if (n && (n.notes || n.notes_translated)) {
      state.notesMd = n.notes + (n.notes_translated && n.language !== 'English' ? `\n\n---\n\n## ${n.language}\n\n${n.notes_translated}` : '');
      $('tab-notes').innerHTML = '<div class="panel-tools"><button class="btn ghost small" id="copyNotes">Copy notes</button></div>' +
        `<div class="md">${md(n.notes)}</div>` + (n.notes_translated && n.language !== 'English' ? `<hr style="border:0;border-top:1px solid var(--line);margin:22px 0"><h3>${esc(n.language)}</h3><div class="md">${md(n.notes_translated)}</div>` : '');
      $('copyNotes').addEventListener('click', async () => { try { await navigator.clipboard.writeText(state.notesMd); toast('Notes copied.'); } catch (_) { toast('Could not copy. Select the text and copy it.'); } });
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
      saveBlob((kind === 'notes' ? 'revision-notes-' : 'gap-report-') + state.sessionId + '.docx', blob);
      toast(kind === 'notes' ? 'Revision notes saved to your Downloads folder.' : 'Gap report saved. Upload this file later to be tested on these gaps.');
    } catch (err) {
      toast(err.message);
    } finally { btn.disabled = false; btn.textContent = old; }
  }
  $('downloadBtn').addEventListener('click', () => downloadDoc('gaps', $('downloadBtn')));
  $('fullDocBtn').addEventListener('click', () => downloadDoc('notes', $('fullDocBtn')));
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
      serverHasKey = !!h.server_key;
      b.classList.remove('bad'); b.classList.toggle('fake', !!h.fake_ai);
      const n = typeof h.requests === 'number' ? ' · ' + h.requests + ' req' : '';
      if (h.using_own_key) {
        b.textContent = 'Your key · ' + h.model + n;
        b.title = 'You are using your own Gemini key. Requests made with it since the server started: ' + h.requests + '. Click to manage your key.';
      } else if (!h.server_key) {
        b.classList.add('bad'); b.textContent = 'Add your Gemini key';
        b.title = 'This site needs your own Gemini API key. Click to add it.';
      } else {
        b.textContent = h.model + n;
        b.title = 'Shared Gemini model: ' + h.model + '. Requests used by everyone since the server started: ' + h.requests + '. A full session uses about 7 and the free tier allows roughly 20 per day per model. Add your own key (top bar) for your own allowance.';
      }
      state.needsKey = !h.server_key && !h.using_own_key;
      $('keyBtn').textContent = h.using_own_key ? '🔑 Your key ✓' : '🔑 API key';
      if (!$('keyModal').hidden) paintKeyUsage(h);
    } catch (_) { b.classList.add('bad'); b.textContent = 'Backend not reachable'; }
    b.hidden = false;
  }

  // ---- AI problems (out of quota, bad key, Gemini busy ...) get a clear card instead of an error string
  const AI_PROBLEMS = {
    quota: ['📭', 'Out of free requests'], bad_key: ['🔑', 'Key not accepted'], busy: ['⏳', 'Gemini is busy'],
    network: ['📡', 'Cannot reach Gemini'], blocked: ['🛡', 'Gemini would not answer that'], unknown: ['⚠', 'The AI hit a problem'],
  };
  let aiShown = { msg: '', at: 0 }, keyChecking = false;
  // When a request fails because the key ran out (or is wrong), the action that failed is remembered here.
  // After a working key is saved the page runs it again, so the student carries on where they left off.
  const resume = { fn: null, at: 0, armed: false };
  const KEY_FIXABLE = ['quota', 'bad_key'];
  function setResume(err, fn) { if (err && KEY_FIXABLE.includes(err.code)) { resume.fn = fn; resume.at = Date.now(); } }
  window.addEventListener('vocalis:aierror', e => {
    const { code, message } = e.detail;
    if (keyChecking) return;                    // the key box shows its own message while testing a key
    aiShown = { msg: message, at: Date.now() };
    // wait one tick so the code that made the request can register what to redo
    setTimeout(() => {
      const canResume = !!resume.fn && Date.now() - resume.at < 600000;
      if (code === 'bad_key') { resume.armed = canResume; openKeyModal(message + (canResume ? ' Paste a working key and you will carry on where you left off.' : '')); return; }
      if (code === 'quota' && canResume) {
        resume.armed = true;
        openKeyModal('This key has used up its free Gemini requests for now. Your answers so far are saved. Paste a key from a different Google account or project and you will carry on exactly where you left off.');
        return;
      }
      showAiCard(code, message);
    }, 0);
  });
  function showAiCard(code, message) {
    const [icon, title] = AI_PROBLEMS[code] || AI_PROBLEMS.unknown;
    $('aiIcon').textContent = icon; $('aiTitle').textContent = title; $('aiText').textContent = message;
    $('aiKey').hidden = code !== 'quota';
    $('aiModal').hidden = false;
  }
  $('aiClose').addEventListener('click', () => { $('aiModal').hidden = true; });
  $('aiKey').addEventListener('click', () => { $('aiModal').hidden = true; openKeyModal(); });
  $('aiModal').addEventListener('click', e => { if (e.target === $('aiModal')) $('aiModal').hidden = true; });

  // a key must exist before anything that calls Gemini (the page asks for it instead of failing later)
  let serverHasKey = false;
  function needKey() {
    if (serverHasKey || V.api.getKey()) return false;
    openKeyModal('Paste your free Gemini API key to start. It takes about a minute to get one.');
    return true;
  }

  // ---- bring your own Gemini key (stored in this browser only)
  function paintKeyUsage(h) {
    const box = $('keyUsage');
    box.hidden = !h.using_own_key;
    if (h.using_own_key) box.textContent = `Requests made with your key: ${h.requests}. About ${Math.max(0, 20 - h.requests)} left today on the free tier (roughly 20 per model per day).`;
  }
  async function openKeyModal(reason) {
    if (!reason) resume.armed = false;          // opened by hand from the top bar: do not redo anything afterwards
    $('keyModal').hidden = false; $('keyMsg').textContent = reason || ''; $('keyMsg').className = 'key-msg';
    $('keyInput').value = V.api.getKey(); $('keyInput').type = 'password'; $('keyShow').textContent = 'Show';
    $('keyInput').focus(); showMode();
  }
  const closeKeyModal = () => { $('keyModal').hidden = true; };
  $('keyBtn').addEventListener('click', () => openKeyModal());
  $('modeBadge').addEventListener('click', () => { if (!$('topbar').hidden) openKeyModal(); });
  $('keyClose').addEventListener('click', closeKeyModal);
  $('keyModal').addEventListener('click', e => { if (e.target === $('keyModal')) closeKeyModal(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && !$('keyModal').hidden) closeKeyModal(); });
  $('keyShow').addEventListener('click', () => { const t = $('keyInput'); t.type = t.type === 'password' ? 'text' : 'password'; $('keyShow').textContent = t.type === 'password' ? 'Show' : 'Hide'; });
  $('keySave').addEventListener('click', async () => {
    const k = $('keyInput').value.trim(), msg = $('keyMsg');
    if (!k) { msg.textContent = 'Paste your key first.'; msg.className = 'key-msg bad'; return; }
    $('keySave').disabled = true; keyChecking = true; msg.textContent = 'Testing your key…'; msg.className = 'key-msg';
    V.api.setKey(k);
    try {
      const r = await V.api.checkKey();
      msg.className = 'key-msg ok'; showMode();
      const redo = resume.armed && resume.fn && Date.now() - resume.at < 600000 ? resume.fn : null;
      if (redo) {
        msg.textContent = '✓ Your key works (' + r.model + '). Carrying on where you left off…';
        resume.fn = null; resume.armed = false;
        setTimeout(() => { closeKeyModal(); toast('Back on track.'); redo(); }, 900);
      } else msg.textContent = '✓ Your key works (' + r.model + '). You can close this and carry on.';
    } catch (e) {
      V.api.setKey('');
      msg.textContent = e.message; msg.className = 'key-msg bad';
    } finally { $('keySave').disabled = false; keyChecking = false; }
  });
  $('keyRemove').addEventListener('click', () => { V.api.setKey(''); $('keyInput').value = ''; $('keyMsg').textContent = 'Your key was removed from this browser.'; $('keyMsg').className = 'key-msg'; showMode(); });
  window.addEventListener('vocalis:nokey', () => openKeyModal('This site needs a Gemini API key to ask questions. Add yours to continue.'));

  let modeTimer;
  window.addEventListener('vocalis:ai', () => { clearTimeout(modeTimer); modeTimer = setTimeout(showMode, 600); });

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
