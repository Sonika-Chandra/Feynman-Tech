/*
  Live speech-to-text in the browser (Chrome and Edge). It is free and instant, so most answers need no
  server-side transcription. If the browser has no speech recognition, the recording is sent to the backend instead.
*/
window.Vocalis = window.Vocalis || {};

window.Vocalis.speech = (() => {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  let rec = null, active = false, finalText = '', interim = '', listener = () => {};

  const current = () => (finalText + ' ' + interim).replace(/\s+/g, ' ').trim();

  function start(lang) {
    finalText = ''; interim = ''; listener('');
    if (!SR) return;
    rec = new SR();
    rec.lang = lang || 'en-IN';
    rec.continuous = true;
    rec.interimResults = true;
    rec.onresult = e => {
      interim = '';
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const r = e.results[i];
        if (r.isFinal) finalText += ' ' + r[0].transcript; else interim += ' ' + r[0].transcript;
      }
      listener(current());
    };
    rec.onend = () => { if (active) { try { rec.start(); } catch (_) {} } };   // the browser stops after silence: keep going
    rec.onerror = () => {};
    active = true;
    try { rec.start(); } catch (_) {}
  }

  function pause() { active = false; try { rec && rec.stop(); } catch (_) {} }
  function resume() { if (!SR || !rec) return; active = true; try { rec.start(); } catch (_) {} }

  function stop() {
    active = false;
    return new Promise(resolve => {
      if (!rec) { resolve(''); return; }
      let done = false;
      const finish = () => { if (!done) { done = true; resolve(current()); } };
      rec.onend = finish;
      try { rec.stop(); } catch (_) { finish(); }
      setTimeout(finish, 1200);
    });
  }

  return { supported: !!SR, start, pause, resume, stop, onUpdate: fn => { listener = fn; } };
})();
