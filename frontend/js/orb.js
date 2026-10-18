/*
  The background orb on the chat screen. It breathes gently when idle, swells and ripples with the volume of your voice
  while you speak, swirls while the AI is thinking and pulses while a question is read aloud.
*/
window.Vocalis = window.Vocalis || {};

window.Vocalis.orb = (() => {
  let cv, ctx, w = 0, h = 0, dpr = 1, mode = 'idle', analyser = null, buf = null, smooth = 0, t = 0, on = false, last = 0;

  function resize() {
    if (!cv) return;
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    w = window.innerWidth; h = window.innerHeight;
    cv.width = w * dpr; cv.height = h * dpr;
  }

  function setAnalyser(a) { analyser = a; buf = a ? new Uint8Array(a.fftSize) : null; }
  function setMode(m) { mode = m; }

  function measure() {
    if (analyser) {
      analyser.getByteTimeDomainData(buf);
      let sum = 0;
      for (let i = 0; i < buf.length; i++) { const x = (buf[i] - 128) / 128; sum += x * x; }
      return Math.min(1, Math.sqrt(sum / buf.length) * 5);
    }
    if (mode === 'speaking') return .38 + .26 * Math.sin(t * 9) * Math.sin(t * 2.7);
    if (mode === 'thinking') return .14 + .1 * Math.sin(t * 4);
    if (mode === 'listening') return .12 + .06 * Math.sin(t * 3);
    return 0;
  }

  // Hollow, thick, soft loops like drifting ribbons. Each loop is a ring whose colour slides around it
  // through shades of maroon, rose and blush. At rest they drift gently; your voice makes them swell and wobble.
  const PALETTES = [
    [[0, '#ff7a96'], [0.35, '#c2183f'], [0.7, '#7a0f2b'], [1, '#ff7a96']],
    [[0, '#ffc2cf'], [0.4, '#e0405f'], [0.75, '#8f1233'], [1, '#ffc2cf']],
    [[0, '#b3123a'], [0.5, '#ff8fa6'], [1, '#b3123a']]
  ];

  function ribbon(cx, cy, r, level, k) {
    const n = 200, rot = t * (0.35 + k * 0.12) * (k % 2 ? -1 : 1), ph = k * 2.1;
    const amp = 0.035 + level * 0.1;
    ctx.beginPath();
    for (let i = 0; i <= n; i++) {
      const a = (i / n) * Math.PI * 2;
      const wob = amp * (Math.sin(2 * a + t * (0.8 + k * 0.3) + ph) * 1.2
                       + Math.sin(3 * a - t * (1.1 + k * 0.2) + ph * 1.5)
                       + level * Math.sin(5 * a + t * 3 + ph) * 0.6);
      const rr = r * (1 + wob);
      const x = cx + Math.cos(a) * rr + Math.sin(t * 0.7 + ph) * r * 0.035;
      const y = cy + Math.sin(a) * rr + Math.cos(t * 0.6 + ph) * r * 0.035;
      i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
    }
    ctx.closePath();
    let stroke;
    if (ctx.createConicGradient) {
      stroke = ctx.createConicGradient(rot, cx, cy);
      PALETTES[k % 3].forEach(([o, c]) => stroke.addColorStop(o, c));
    } else stroke = PALETTES[k % 3][1][1];
    ctx.strokeStyle = stroke;
    ctx.lineJoin = 'round';
    // soft outer haze, then the solid ribbon on top
    ctx.globalAlpha = 0.16; ctx.lineWidth = 34 + level * 22; ctx.shadowBlur = 0; ctx.stroke();
    ctx.globalAlpha = 0.8; ctx.lineWidth = 15 + level * 10; ctx.shadowColor = 'rgba(255,120,150,.55)'; ctx.shadowBlur = 20; ctx.stroke();
    ctx.shadowBlur = 0; ctx.globalAlpha = 1;
  }

  function sphere(cx, cy, r, level) {
    ribbon(cx, cy, r * 1.05, level, 0);
    ribbon(cx, cy, r * 0.98, level, 1);
    ribbon(cx, cy, r * 1.0, level, 2);
  }

  function frame(now) {
    if (!on) return;
    requestAnimationFrame(frame);
    const dt = Math.min(0.05, (now - last) / 1000 || 0.016); last = now;
    t += dt * (mode === 'thinking' ? 1.8 : 1);
    const target = measure();
    smooth += (target - smooth) * (target > smooth ? 0.35 : 0.08);   // quick to swell, slow to settle
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    const cx = w * 0.5, cy = h * 0.5 + 6 * Math.sin(t * 1.1);
    const r = Math.min(w, h) * 0.17 * (1 + 0.02 * Math.sin(t * 1.4) + smooth * 0.18);
    sphere(cx, cy, r, smooth);
  }

  function enable(flag) {
    if (!cv) { cv = document.getElementById('orb'); if (!cv) return; ctx = cv.getContext('2d'); window.addEventListener('resize', resize); }
    if (flag && !on) { on = true; resize(); last = performance.now(); requestAnimationFrame(frame); }
    if (!flag) on = false;
  }

  return { enable, setAnalyser, setMode };
})();
