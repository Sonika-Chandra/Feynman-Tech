/*
  Whiteboard. The student draws with a mouse, pen or finger: freehand, lines, arrows, boxes, circles, typed labels,
  axes and graph paper. Everything is kept as a list of items so Undo and window resizing are exact.
  toBlob() gives a PNG (dark ink on beige paper) that is sent to the AI together with the written or spoken answer.
*/
window.Vocalis = window.Vocalis || {};

window.Vocalis.whiteboard = (() => {
  const PAPER = '#f1e7d0';
  const $ = id => document.getElementById(id);
  let cv, ctx, ink, inkCtx, stage, textInput;
  let items = [], draft = null, tool = 'pen', color = '#1b1214', size = 4, grid = false, drawing = false, dpr = 1;
  let pendingText = null;   // {pt:{x,y}, mark:boolean}
  let bg = null;            // {img, ratio, ready}: a diagram drawn by the AI, shown behind the student's ink
  let onChange = () => {};

  // ---------------------------------------------------------------- drawing items
  function drawItem(c, it) {
    c.save();
    c.lineCap = 'round'; c.lineJoin = 'round';
    c.strokeStyle = it.color; c.fillStyle = it.color; c.lineWidth = it.size;
    if (it.type === 'erase') {
      c.globalCompositeOperation = 'destination-out';
      c.lineWidth = it.size * 4;
    }
    if (it.type === 'pen' || it.type === 'erase') {
      c.beginPath();
      it.pts.forEach((p, i) => i ? c.lineTo(p.x, p.y) : c.moveTo(p.x, p.y));
      if (it.pts.length === 1) c.lineTo(it.pts[0].x + .01, it.pts[0].y);
      c.stroke();
    } else if (it.type === 'line' || it.type === 'arrow') {
      c.beginPath(); c.moveTo(it.a.x, it.a.y); c.lineTo(it.b.x, it.b.y); c.stroke();
      if (it.type === 'arrow') {
        const ang = Math.atan2(it.b.y - it.a.y, it.b.x - it.a.x), h = 10 + it.size * 2;
        c.beginPath();
        c.moveTo(it.b.x, it.b.y);
        c.lineTo(it.b.x - h * Math.cos(ang - .45), it.b.y - h * Math.sin(ang - .45));
        c.moveTo(it.b.x, it.b.y);
        c.lineTo(it.b.x - h * Math.cos(ang + .45), it.b.y - h * Math.sin(ang + .45));
        c.stroke();
      }
    } else if (it.type === 'rect') {
      c.strokeRect(it.a.x, it.a.y, it.b.x - it.a.x, it.b.y - it.a.y);
    } else if (it.type === 'ellipse') {
      c.beginPath();
      c.ellipse((it.a.x + it.b.x) / 2, (it.a.y + it.b.y) / 2, Math.abs(it.b.x - it.a.x) / 2, Math.abs(it.b.y - it.a.y) / 2, 0, 0, Math.PI * 2);
      c.stroke();
    } else if (it.type === 'mark') {
      c.beginPath(); c.arc(it.a.x, it.a.y, 5 + it.size / 2, 0, Math.PI * 2); c.fill();
      if (it.text) {
        c.font = '700 ' + it.px + 'px Manrope, system-ui, sans-serif';
        c.textBaseline = 'middle';
        c.fillText(it.text, it.a.x + 12, it.a.y - 10);
      }
    } else if (it.type === 'text') {
      c.font = '600 ' + it.px + 'px Manrope, system-ui, sans-serif';
      c.textBaseline = 'top';
      c.fillText(it.text, it.a.x, it.a.y);
    }
    c.restore();
  }

  function paintGrid(c, w, h) {
    c.save();
    c.strokeStyle = 'rgba(109,26,43,.14)'; c.lineWidth = 1;
    for (let x = 0; x <= w; x += 28) { c.beginPath(); c.moveTo(x + .5, 0); c.lineTo(x + .5, h); c.stroke(); }
    for (let y = 0; y <= h; y += 28) { c.beginPath(); c.moveTo(0, y + .5); c.lineTo(w, y + .5); c.stroke(); }
    c.restore();
  }

  function render(forExport) {
    const w = cv.width / dpr, h = cv.height / dpr;
    inkCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
    inkCtx.clearRect(0, 0, w, h);
    items.concat(draft ? [draft] : []).forEach(it => drawItem(inkCtx, it));
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = PAPER; ctx.fillRect(0, 0, w, h);
    if (grid && !forExport) paintGrid(ctx, w, h);
    if (bg && bg.ready) {
      const maxW = w * 0.9, maxH = h * 0.9;
      let dw = maxW, dh = dw / bg.ratio;
      if (dh > maxH) { dh = maxH; dw = dh * bg.ratio; }
      ctx.drawImage(bg.img, (w - dw) / 2, (h - dh) / 2, dw, dh);
    }
    ctx.drawImage(ink, 0, 0, w, h);
  }

  function resize() {
    const r = cv.getBoundingClientRect();
    if (r.width < 10 || r.height < 10) return;
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    cv.width = Math.round(r.width * dpr); cv.height = Math.round(r.height * dpr);
    ink.width = cv.width; ink.height = cv.height;
    render();
  }

  // ---------------------------------------------------------------- pointer handling
  function pos(e) {
    const r = cv.getBoundingClientRect();
    return { x: e.clientX - r.left, y: e.clientY - r.top };
  }

  function commitText() {
    if (!pendingText) return;
    const v = textInput.value.trim();
    if (pendingText.mark) {
      items.push({ type: 'mark', text: v, a: pendingText.pt, color, px: 15 + size * 1.4, size });
      onChange();
    } else if (v) {
      items.push({ type: 'text', text: v, a: pendingText.pt, color, px: 14 + size * 1.6, size });
      onChange();
    }
    textInput.hidden = true; textInput.value = ''; pendingText = null;
    render();
  }

  function placeText(e) {
    if (tool !== 'text' && tool !== 'mark') return;
    commitText();
    const p = pos(e), mark = tool === 'mark';
    pendingText = { pt: p, mark };
    textInput.style.left = (cv.offsetLeft + p.x + (mark ? 12 : 0)) + 'px';
    textInput.style.top = (cv.offsetTop + p.y - (mark ? 26 : 6)) + 'px';
    textInput.placeholder = mark ? 'Name this point, then Enter' : 'Type, then Enter';
    textInput.hidden = false;
    textInput.focus();
  }

  function down(e) {
    if (e.button !== undefined && e.button > 0) return;
    if (tool === 'text' || tool === 'mark') return;      // labels and marks are placed on 'click', after the browser has finished moving focus
    commitText();
    cv.setPointerCapture(e.pointerId);
    drawing = true;
    const p = pos(e);
    if (tool === 'pen') draft = { type: 'pen', color, size, pts: [p] };
    else if (tool === 'eraser') draft = { type: 'erase', color: '#000', size, pts: [p] };
    else draft = { type: tool, color, size, a: p, b: p };
    render();
  }
  function move(e) {
    if (!drawing || !draft) return;
    const p = pos(e);
    if (draft.pts) draft.pts.push(p); else draft.b = p;
    render();
  }
  function up() {
    if (!drawing) return;
    drawing = false;
    if (draft) {
      const tiny = !draft.pts && Math.hypot(draft.b.x - draft.a.x, draft.b.y - draft.a.y) < 3;
      if (!tiny) { items.push(draft); onChange(); }
    }
    draft = null;
    render();
  }

  // ---------------------------------------------------------------- public API
  function init(opts) {
    onChange = (opts && opts.onChange) || onChange;
    cv = $('wbCanvas'); ctx = cv.getContext('2d');
    ink = document.createElement('canvas'); inkCtx = ink.getContext('2d');
    stage = $('wbStage'); textInput = $('wbText');

    cv.addEventListener('pointerdown', down);
    cv.addEventListener('pointermove', move);
    cv.addEventListener('pointerup', up);
    cv.addEventListener('pointercancel', up);
    cv.addEventListener('click', placeText);
    textInput.addEventListener('keydown', e => { if (e.key === 'Enter') commitText(); if (e.key === 'Escape') { textInput.value = ''; commitText(); } });
    textInput.addEventListener('blur', commitText);
    window.addEventListener('resize', () => resize());
    if (window.ResizeObserver) new ResizeObserver(() => resize()).observe(stage);

    document.querySelectorAll('#wbTools .tool[data-tool]').forEach(b => b.addEventListener('click', () => {
      commitText();
      tool = b.dataset.tool;
      document.querySelectorAll('#wbTools .tool[data-tool]').forEach(x => x.classList.toggle('active', x === b));
      cv.style.cursor = (tool === 'text' || tool === 'mark') ? 'text' : 'crosshair';
    }));
    document.querySelectorAll('#wbTools .swatch').forEach(b => b.addEventListener('click', () => {
      color = b.dataset.color;
      document.querySelectorAll('#wbTools .swatch').forEach(x => x.classList.toggle('active', x === b));
    }));
    $('wbSize').addEventListener('input', e => { size = +e.target.value; });
    $('wbGrid').addEventListener('click', e => { grid = !grid; e.currentTarget.setAttribute('aria-pressed', grid); render(); });
    $('wbUndo').addEventListener('click', () => { commitText(); items.pop(); render(); onChange(); });
    $('wbClear').addEventListener('click', () => { clear(); });
    $('wbAxes').addEventListener('click', () => {
      const w = cv.width / dpr, h = cv.height / dpr, m = 40;
      items.push({ type: 'arrow', color: '#1b1214', size: 3, a: { x: m, y: h - m }, b: { x: w - m, y: h - m } });
      items.push({ type: 'arrow', color: '#1b1214', size: 3, a: { x: m, y: h - m }, b: { x: m, y: m } });
      items.push({ type: 'text', text: 'x', a: { x: w - m + 6, y: h - m - 10 }, color: '#1b1214', px: 18, size: 3 });
      items.push({ type: 'text', text: 'y', a: { x: m - 5, y: m - 24 }, color: '#1b1214', px: 18, size: 3 });
      render(); onChange();
    });
    resize();
  }

  /** Shows an AI-drawn SVG behind the board (to label or identify its parts). Pass '' or null to remove it. */
  function setDiagram(svg) {
    if (!svg) { bg = null; if (cv) render(); return; }
    const m = svg.match(/viewBox\s*=\s*["']\s*[-\d.]+\s+[-\d.]+\s+([\d.]+)\s+([\d.]+)/);
    const ratio = m && +m[2] > 0 ? (+m[1]) / (+m[2]) : 4 / 3;
    const img = new Image();
    const entry = { img, ratio, ready: false };
    bg = entry;
    img.onload = () => { entry.ready = true; if (bg === entry) render(); };
    img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
  }

  function clear() { commitText(); items = []; draft = null; render(); onChange(); }
  function hasInk() { return items.length > 0; }

  /** PNG of the board (paper + ink, no grid), max 1200 px wide to keep uploads small. */
  function toBlob() {
    if (!items.length) return Promise.resolve(null);
    commitText();
    render(true);
    const scale = Math.min(1, 1200 / cv.width);
    const out = document.createElement('canvas');
    out.width = Math.round(cv.width * scale); out.height = Math.round(cv.height * scale);
    out.getContext('2d').drawImage(cv, 0, 0, out.width, out.height);
    render();
    return new Promise(resolve => out.toBlob(b => resolve(b), 'image/png'));
  }

  return { init, resize, clear, hasInk, toBlob, setDiagram };
})();
