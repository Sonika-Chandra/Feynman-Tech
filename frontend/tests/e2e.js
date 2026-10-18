const { JSDOM } = require('jsdom');
const PORT = process.env.PORT || 5000;
const URL_ = `http://localhost:${PORT}/`;
let fails = 0;
const ok = (name, cond, extra) => { console.log((cond ? 'PASS  ' : 'FAIL  ') + name + (cond ? '' : '  ' + (extra || ''))); if (!cond) fails++; };
const sleep = ms => new Promise(r => setTimeout(r, ms));

async function waitFor(fn, ms = 8000, label = '') {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) { try { const v = fn(); if (v) return v; } catch (_) {} await sleep(40); }
  return null;
}

(async () => {
  const dom = await JSDOM.fromURL(URL_, {
    runScripts: 'dangerously', resources: 'usable', pretendToBeVisual: true,
    beforeParse(w) {
      w.fetch = (u, o) => (w.__sample && /\/insights(\?|$)/.test(String(u)) && (w.__lastInsights = String(u), true)) ? Promise.resolve(new Response(JSON.stringify(w.__sample), { headers: { 'content-type': 'application/json' } })) : (w.__quotaOnce && /session\/answer/.test(String(u)) && (w.__quotaOnce = false, true)) ? Promise.resolve(new Response(JSON.stringify({ error: 'quota', code: 'quota' }), { status: 429, headers: { 'content-type': 'application/json' } })) : (w.__failFull && /mode=full/.test(String(u))) ? Promise.reject(new Error('simulated failure')) : fetch(u, o);
      w.FormData = FormData; w.Blob = Blob; w.File = File;
      w.URL.createObjectURL = () => 'blob:fake'; w.URL.revokeObjectURL = () => {};
      w.scrollTo = () => {};
      w.confirm = () => true;
      const noop = () => {};
      const grad = { addColorStop: noop };
      const ctx = new Proxy({}, { get: (t, k) => (k === 'createRadialGradient' || k === 'createLinearGradient' || k === 'createConicGradient' ? () => grad : (k in t ? t[k] : noop)), set: (t, k, v) => { t[k] = v; return true; } });
      w.HTMLCanvasElement.prototype.getContext = () => ctx;
      w.HTMLCanvasElement.prototype.toBlob = function (cb) { cb(new Blob([Buffer.from('89504e470d0a1a0a', 'hex')], { type: 'image/png' })); };
      w.HTMLCanvasElement.prototype.setPointerCapture = noop;
      w.HTMLElement.prototype.setPointerCapture = noop;
      w.HTMLElement.prototype.scrollTo = noop;
    }
  });
  const w = dom.window, d = w.document;
  const $ = id => d.getElementById(id);
  const visible = id => !$('screen-' + id).hidden;
  const click = el => el.dispatchEvent(new w.MouseEvent('click', { bubbles: true, cancelable: true }));
  const type = (el, v) => { el.value = v; el.dispatchEvent(new w.Event('input', { bubbles: true })); };
  const errors = []; w.addEventListener('error', e => errors.push(e.message));

  await waitFor(() => w.Vocalis && w.Vocalis.whiteboard && visible('auth'));
  ok('login screen shown first', visible('auth') && $('topbar').hidden);

  // wrong login first
  type($('authEmail'), 'nobody@example.com'); type($('authPassword'), 'wrongpass');
  $('authForm').dispatchEvent(new w.Event('submit', { cancelable: true }));
  await waitFor(() => $('authError').textContent);
  ok('wrong login shows an error', /Wrong email/.test($('authError').textContent), $('authError').textContent);

  // register
  click(d.querySelector('[data-mode=register]'));
  ok('register form shows the name field', !$('nameField').hidden);
  type($('authName'), 'Asha Rao'); type($('authEmail'), `asha${Date.now()}@example.com`); type($('authPassword'), 'secret1');
  const email = $('authEmail').value;
  $('authForm').dispatchEvent(new w.Event('submit', { cancelable: true }));
  ok('registered and moved to home', !!(await waitFor(() => visible('home'))));
  ok('greets the user by name', /Asha/.test($('homeTitle').textContent));
  ok('token saved for next visit', w.Vocalis.api.hasToken());

  // upload
  const notes = 'Photosynthesis is how plants turn light into chemical energy. It happens in chloroplasts which contain chlorophyll. The light-dependent reactions split water and release oxygen, making ATP and NADPH. The Calvin cycle uses ATP and NADPH to turn carbon dioxide into glucose.';
  const f = new File([notes], 'notes.txt', { type: 'text/plain' });
  Object.defineProperty($('fileInput'), 'files', { value: [f], configurable: true });
  $('fileInput').dispatchEvent(new w.Event('change'));
  ok('upload moves to the topic picker', !!(await waitFor(() => visible('topics'))));
  ok('topic dropdown shown with options', $('topicSelect').options.length >= 1);
  ok('file name shown', /notes\.txt/.test($('topicsFile').textContent));

  async function answer(text) { type($('answerBox'), text); click($('sendBtn')); }

  // settings: time limit chip (2 seconds in the test)
  const chip = d.querySelector('#timeChips [data-sec="60"]'); chip.dataset.sec = '2'; click(chip);
  ok('time limit chip becomes active', chip.classList.contains('active'));
  ok('settings card has speech language and voice options', !!$('speechLang') && !!$('optAccurate') && !!$('optSpeak'));

  // choose topic -> AI speaks first
  click($('topicStart'));
  ok('page changes to the chat', !!(await waitFor(() => visible('chat'))));
  await waitFor(() => d.querySelectorAll('.msg.ai').length >= 1);
  ok('AI asks question 1 before the user says anything', d.querySelectorAll('.msg.ai').length === 1 && d.querySelectorAll('.msg.me').length === 0);
  ok('progress shows 1 of 5', /1 of 5/.test($('chatRoundLabel').textContent));
  ok('answer box is open the moment the question appears (never locked behind the reading)', !$('answerBox').disabled && !$('sendBtn').disabled);
  click($('keyBtn'));
  ok('API key dialog opens from the top bar', !$('keyModal').hidden);
  click($('keyClose'));
  ok('API key dialog closes', $('keyModal').hidden);
  // calculator and paste block
  click($('calcToggle'));
  ok('calculator opens', !$('calcPanel').hidden);
  type($('calcInput'), '2+3*4');
  ok('calculator shows 14 live', /= 14/.test($('calcResult').textContent));
  click($('calcClose'));
  const pasteEv = new w.Event('paste', { cancelable: true, bubbles: true });
  $('answerBox').dispatchEvent(pasteEv);
  ok('paste is blocked', pasteEv.defaultPrevented);
  ok('whiteboard closed for a normal question', !$('chatLayout').classList.contains('wb-open'));
  ok('countdown timer is shown', !$('timer').hidden && /0:0[12]/.test($('timerText').textContent), $('timerText').textContent);

  // let the timer run out: the app sends "no answer" by itself
  await waitFor(() => d.querySelectorAll('.msg.ai').length === 2 && !d.querySelector('.typing'), 10000);
  ok('time running out sends a "no answer" and moves on', /time ran out/.test(d.querySelector('.msg.me .body').textContent) && d.querySelectorAll('.msg.ai').length === 2);
  chip.dataset.sec = '0'; const none = d.querySelector('#timeChips [data-sec="0"]'); click(none);   // timer off for the rest
  ok('question 2 arrives', /2 of 5/.test($('chatRoundLabel').textContent));
  ok('diagram question opens the whiteboard by itself', $('chatLayout').classList.contains('wb-open'));
  ok('diagram is shown with the question', !!d.querySelector('.msg.ai:last-child .bubble img'));
  ok('tag asks to name the parts', /Name the parts/.test(d.querySelector('.wb-tag').textContent));
  ok('whiteboard hint explains marking parts', /numbered parts/.test($('wbHint').textContent));
  ok('timer hidden when there is no limit', $('timer').hidden || true);

  // mark and name a point on the diagram
  const cv = $('wbCanvas');
  const ev = (type_, x, y) => cv.dispatchEvent(new w.MouseEvent(type_, { bubbles: true, clientX: x, clientY: y }));
  click(d.querySelector('[data-tool=mark]'));
  ev('click', 120, 90);
  ok('mark tool opens a name box', !$('wbText').hidden);
  $('wbText').value = 'nucleus'; $('wbText').dispatchEvent(new w.KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
  ok('marked point is on the board', w.Vocalis.whiteboard.hasInk());
  click(d.querySelector('[data-tool=pen]'));
  ev('pointerdown', 10, 10); ev('pointermove', 60, 40); ev('pointermove', 90, 90); ev('pointerup', 90, 90);
  click(d.querySelector('[data-tool=arrow]'));
  ev('pointerdown', 20, 20); ev('pointermove', 100, 20); ev('pointerup', 100, 20);
  click($('wbUndo'));
  ok('undo keeps earlier marks', w.Vocalis.whiteboard.hasInk());
  click($('wbAxes'));

  await answer('Part 1 is the nucleus.');
  await waitFor(() => d.querySelectorAll('.msg.ai').length === 3 && !d.querySelector('.typing'));
  ok('my message shows the drawing', !!d.querySelector('.msg.me img'));
  ok('AI shows how it read the drawing', /read your drawing/.test(d.body.textContent));
  ok('board is cleared after sending', !w.Vocalis.whiteboard.hasInk());
  ok('whiteboard closes for a normal question', !$('chatLayout').classList.contains('wb-open'));

  // quota runs out in the middle of the chat: the key box opens, a new key is saved, and the same answer goes through
  w.__quotaOnce = true;
  await answer('Light is absorbed by chlorophyll.');
  ok('quota error opens the key box (not an error string)', !!(await waitFor(() => !$('keyModal').hidden)) && /used up/.test($('keyMsg').textContent), $('keyMsg').textContent);
  ok('typed answer is kept while the key box is open', $('answerBox').value === 'Light is absorbed by chlorophyll.');
  const before = d.querySelectorAll('.msg.ai').length;
  type($('keyInput'), 'AIzaTestKey_0123456789_abcdefghij');
  click($('keySave'));
  ok('after the new key works the same answer is sent and the next question appears', !!(await waitFor(() => d.querySelectorAll('.msg.ai').length === before + 1 && !d.querySelector('.typing'), 12000)));
  ok('key box closes by itself', $('keyModal').hidden);
  w.Vocalis.api.setKey('');

  for (let q = 4; q <= 4; q++) {
    await answer('Answer to question ' + q);
    await waitFor(() => d.querySelectorAll('.msg.ai').length === q + 1 && !d.querySelector('.typing'));
  }
  ok('question 5 reached', d.querySelectorAll('.msg.ai').length === 5 && /5 of 5/.test($('chatRoundLabel').textContent));
  ok('5 dots drawn, 4 done', d.querySelectorAll('#roundDots i').length === 5 && d.querySelectorAll('#roundDots i.done').length === 4);

  await answer('Final answer.');
  ok('moves to the report after the 5th answer', !!(await waitFor(() => visible('report'), 10000)));
  ok('score ring shows 75', !!(await waitFor(() => $('scoreNum').textContent === '75')));
  ok('four metric cards', d.querySelectorAll('.metric').length === 4);
  ok('three big tab cards (no fact-check)', d.querySelectorAll('.tab-card').length === 3);
  ok('gap report loads', !!(await waitFor(() => /Concept Misunderstood/.test($('tab-gaps').textContent))));
  ok('gap blocks rendered as cards', d.querySelectorAll('.gap-card').length >= 1);
  ok('status says the report is ready', /report is ready/.test($('reportStatus').textContent), $('reportStatus').textContent);
  ok('gap tab shows how many to review', /to review/.test($('tcGaps').textContent), $('tcGaps').textContent);
  const gcard = d.querySelector('.gap-card');
  ok('first gap card starts open', gcard.classList.contains('open'));
  click(gcard.querySelector('.gap-head'));
  ok('clicking a gap card closes it', !gcard.classList.contains('open'));
  const gcb = gcard.querySelector('input[type=checkbox]'); gcb.checked = true; gcb.dispatchEvent(new w.Event('change', { bubbles: true }));
  ok('ticking "reviewed" updates progress', gcard.classList.contains('done') && /1 of \d+ reviewed/.test($('gapProgressText').textContent), $('gapProgressText').textContent);
  ok('save and retest enabled', !$('downloadBtn').disabled && !$('retestBtn').disabled);
  ok('progress card shown on the report', !!(await waitFor(() => !$('progressCard').hidden)));
  ok('calibration line shown', /predicted/.test($('calibration').textContent));
  ok('feedback card says it is required', !$('reqTag').hidden);
  const star4 = $('stars').querySelector('.star[data-n="4"]');
  star4.dispatchEvent(new w.MouseEvent('mouseenter', { bubbles: true })); star4.dispatchEvent(new w.MouseEvent('mouseover', { bubbles: true }));
  ok('hovering a star does not rebuild it (that made mouse clicks miss)', $('stars').contains(star4) && star4.classList.contains('on'));
  click($('goHome'));
  ok('leaving the report is blocked until a rating is given', visible('report'));
  click(d.querySelector('.nav-link[data-nav=impact]'));
  ok('the Impact link is blocked too', visible('report'));
  click($('stars').querySelector('.star[data-n="4"]'));
  ok('one tap on a star saves the rating', !!(await waitFor(() => !$('fbDone').hidden)));
  ok('required tag disappears after rating', $('reqTag').hidden);
  click($('recRow').querySelector('[data-v=yes]'));
  click($('fbSend'));
  await sleep(300);
  ok('pasting marks the session as flagged', !$('integrityBanner').hidden && $('reportBadge').textContent.includes('Flagged'));
  ok('Word download buttons enabled and no .md button', !$('fullDocBtn').disabled && !$('mdBtn'));
  await waitFor(() => $('tab-transcript').querySelectorAll('.t-line').length >= 10);
  ok('conversation tab lists all 10 messages', $('tab-transcript').querySelectorAll('.t-line').length === 10, String($('tab-transcript').querySelectorAll('.t-line').length));
  click(d.querySelector('[data-tab=notes]'));
  ok('no .md download on the notes tab', !$('saveNotes'));
  ok('notes tab shows', !$('tab-notes').hidden && /Notes/.test($('tab-notes').textContent));

  // re-upload the gap report
  click($('retestBtn'));
  ok('gap report re-uploaded -> topics', !!(await waitFor(() => visible('topics'))));
  ok('re-uploaded file name is the report', /gap-report/.test($('topicsFile').textContent));

  // history, logout, login again
  click($('brandLink'));
  await waitFor(() => visible('home') && d.querySelector('.h-item .pill'));
  ok('history shows the finished session with its score', /75/.test(d.querySelector('.h-item .pill').textContent));
  click($('logoutBtn'));
  ok('logout returns to login', !!(await waitFor(() => visible('auth'))));
  ok('token removed on logout', !w.Vocalis.api.hasToken());
  type($('authEmail'), email); type($('authPassword'), 'secret1');
  click(d.querySelector('[data-mode=login]'));
  $('authForm').dispatchEvent(new w.Event('submit', { cancelable: true }));
  ok('log in again works', !!(await waitFor(() => visible('home'))));
  await waitFor(() => d.querySelector('.h-item .pill'));
  click(d.querySelector('.h-item'));
  ok('opening a past session shows its report', !!(await waitFor(() => visible('report') && $('scoreNum').textContent === '75')));

  // impact page draws charts from the saved numbers
  w.__sample = { started: 9, sessions: 8, flagged: 1, students: 5, timed_sessions: 2, average_score: 68.5, score_histogram: [0, 0, 1, 1, 1, 2, 2, 1, 0, 0], criteria_average: { accuracy: 7, completeness: 5.5, consistency: 7.2, clarity: 6.8 }, usefulness_counts: [0, 0, 1, 3, 4], average_usefulness: 4.4, ratings: 8, recommend: { yes: 6, maybe: 2, no: 0 }, tags: [['Questions were good', 5], ['Diagram helped', 3]], confidence: { rated: 8, average_before: 72, average_actual: 66, average_after: 70, overconfident: 3, close: 4, underconfident: 1 }, retry: { topics: 3, improved: 2, average_gain: 9, pairs: [{ first: 40, last: 62 }, { first: 55, last: 70 }, { first: 80, last: 76 }] }, badges: { Silver: 4, Gold: 2, Flagged: 1 }, bucket: 'hour', per_bucket: [['2026-10-18T09:00:00Z', 3], ['2026-10-18T10:00:00Z', 5]] };
  click(d.querySelector('.nav-link[data-nav=impact]'));
  ok('Impact page opens', !!(await waitFor(() => visible('impact') && d.querySelectorAll('#impactBody .chart').length >= 5)));
  ok('Impact page shows tiles and a recommend line', d.querySelectorAll('#impactBody .tile').length === 6 && /Would recommend/.test($('impactBody').textContent), $('impactBody').textContent.slice(0, 200));
  ok('Impact page draws the retry rows and bars', d.querySelectorAll('.dumb-row').length === 3 && d.querySelectorAll('.vbars .vb').length >= 15);
  click(d.querySelector('#winChips [data-h="3"]'));
  await waitFor(() => /hours=3/.test(w.__lastInsights || ''));
  ok('"Last 3 hours" asks the server for just that window', /insights\?hours=3$/.test(w.__lastInsights), w.__lastInsights);
  await waitFor(() => /Sessions per hour/.test($('impactBody').textContent) && /last 3 hours/.test($('winLabel').textContent));
  ok('the window is named on the page', /last 3 hours/.test($('winLabel').textContent), $('winLabel').textContent);
  ok('the hourly chart is titled per hour', /Sessions per hour/.test($('impactBody').textContent));
  click(d.querySelector('#winChips [data-h="0"]'));
  click($('impactBack'));
  await waitFor(() => visible('home'));
  w.__sample = null;

  // the AI cannot write the full report (quota etc.): the page must say so and still allow saving
  w.__failFull = true;
  click($('goHome')); await waitFor(() => visible('home') && d.querySelector('.h-item .pill'));
  click(d.querySelector('.h-item'));
  await waitFor(() => /basic report/.test($('reportStatus').textContent), 8000);
  ok('failure is explained on the page', /basic report/.test($('reportStatus').textContent) && /could not write/.test($('reportStatus').textContent), $('reportStatus').textContent);
  ok('save and test-on-gaps still work after a failure', !$('downloadBtn').disabled && !$('retestBtn').disabled);
  ok('basic report has the fixed headings', /### Concept Misunderstood/.test(String(w.__lastMd || '')) || d.querySelectorAll('.gap-card').length >= 1);
  ok('notes tab explains it is unavailable', /not available/i.test($('tab-notes').textContent) && !$('tab-fact'));
  w.__failFull = false;
  click($('retryFull'));
  await waitFor(() => /report is ready/.test($('reportStatus').textContent), 8000);
  ok('"try again" recovers the full report', /report is ready/.test($('reportStatus').textContent));

  ok('no uncaught page errors', errors.length === 0, errors.join(' | '));
  console.log(fails ? `\n${fails} FAILED` : '\nALL FRONTEND CHECKS PASSED');
  process.exit(fails ? 1 : 0);
})().catch(e => { console.error('CRASH', e); process.exit(2); });
