/* Scientific calculator. Uses its own small expression parser (no eval), so only maths can run. */
window.Vocalis = window.Vocalis || {};

window.Vocalis.calc = (() => {
  const FN = {
    sin: x => Math.sin(toRad(x)), cos: x => Math.cos(toRad(x)), tan: x => Math.tan(toRad(x)),
    asin: x => fromRad(Math.asin(x)), acos: x => fromRad(Math.acos(x)), atan: x => fromRad(Math.atan(x)),
    sinh: Math.sinh, cosh: Math.cosh, tanh: Math.tanh,
    ln: Math.log, log: Math.log10, sqrt: Math.sqrt, cbrt: Math.cbrt, abs: Math.abs, exp: Math.exp,
    floor: Math.floor, ceil: Math.ceil, round: Math.round,
  };
  let degrees = true, last = 0;
  const toRad = x => degrees ? x * Math.PI / 180 : x;
  const fromRad = x => degrees ? x * 180 / Math.PI : x;

  function fact(n) {
    if (n < 0 || Math.abs(n - Math.round(n)) > 1e-9 || n > 170) throw new Error('n! needs 0 to 170');
    let r = 1; for (let i = 2; i <= Math.round(n); i++) r *= i; return r;
  }

  /** expression := term (('+'|'-') term)* ; term := power (('*'|'/') power)* ; power := unary ('^' power)? ; postfix ! and % */
  function evaluate(src) {
    const s = src.replace(/×/g, '*').replace(/÷/g, '/').replace(/−/g, '-').replace(/π/g, 'pi').replace(/√/g, 'sqrt').replace(/\s+/g, '');
    let i = 0;
    const peek = () => s[i];
    function num() {
      const m = /^(\d+\.?\d*|\.\d+)(e[+-]?\d+)?/i.exec(s.slice(i));
      if (!m) throw new Error('Unexpected "' + (s[i] || 'end') + '"');
      i += m[0].length; return parseFloat(m[0]);
    }
    function primary() {
      let v;
      if (peek() === '(') { i++; v = expr(); if (peek() !== ')') throw new Error('Missing )'); i++; }
      else if (/[a-z]/i.test(peek() || '')) {
        const m = /^[a-z]+/i.exec(s.slice(i))[0].toLowerCase(); i += m.length;
        if (m === 'pi') v = Math.PI; else if (m === 'e') v = Math.E; else if (m === 'ans') v = last;
        else if (FN[m]) { if (peek() !== '(') throw new Error(m + ' needs ( )'); i++; const a = expr(); if (peek() !== ')') throw new Error('Missing )'); i++; v = FN[m](a); }
        else throw new Error('Unknown "' + m + '"');
      } else v = num();
      while (peek() === '!' || peek() === '%') { v = s[i++] === '!' ? fact(v) : v / 100; }
      return v;
    }
    function unary() { if (peek() === '-') { i++; return -unary(); } if (peek() === '+') { i++; return unary(); } return power(); }
    function power() { const b = primary(); if (peek() === '^') { i++; return Math.pow(b, unary()); } return b; }
    function term() {
      let v = unary();
      for (;;) {
        const c = peek();
        if (c === '*') { i++; v *= unary(); } else if (c === '/') { i++; v /= unary(); }
        else if (c === '(' || (c && /[a-z]/i.test(c))) v *= power();       // 2(3+4) and 2pi
        else return v;
      }
    }
    function expr() { let v = term(); while (peek() === '+' || peek() === '-') v = s[i++] === '+' ? v + term() : v - term(); return v; }
    const out = expr();
    if (i < s.length) throw new Error('Unexpected "' + s[i] + '"');
    if (!isFinite(out)) throw new Error('Not a real number');
    return out;
  }

  const fmt = n => String(parseFloat(n.toPrecision(12)));

  function mount(root) {
    const disp = root.querySelector('#calcInput'), res = root.querySelector('#calcResult'), hist = root.querySelector('#calcHist');
    const mode = root.querySelector('#calcMode');
    const run = () => {
      try { const v = evaluate(disp.value); last = v; res.textContent = '= ' + fmt(v); res.classList.remove('bad');
        hist.insertAdjacentHTML('afterbegin', '<div></div>'); hist.firstChild.textContent = disp.value + ' = ' + fmt(v); }
      catch (e) { res.textContent = e.message; res.classList.add('bad'); }
    };
    const put = t => { const a = disp.selectionStart ?? disp.value.length, b = disp.selectionEnd ?? a; disp.value = disp.value.slice(0, a) + t + disp.value.slice(b); const p = a + t.length; disp.setSelectionRange(p, p); disp.focus(); live(); };
    const live = () => { try { if (disp.value.trim()) res.textContent = '= ' + fmt(evaluate(disp.value)); else res.textContent = ''; res.classList.remove('bad'); } catch (_) { res.textContent = ''; } };
    root.querySelectorAll('[data-k]').forEach(b => b.addEventListener('click', () => put(b.dataset.k)));
    root.querySelector('#calcEq').addEventListener('click', run);
    root.querySelector('#calcClear').addEventListener('click', () => { disp.value = ''; res.textContent = ''; disp.focus(); });
    root.querySelector('#calcBack').addEventListener('click', () => { disp.value = disp.value.slice(0, -1); live(); disp.focus(); });
    mode.addEventListener('click', () => { degrees = !degrees; mode.textContent = degrees ? 'DEG' : 'RAD'; live(); });
    disp.addEventListener('input', live);
    disp.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); e.stopPropagation(); run(); } });
    return { insertInto: target => { const t = res.textContent.replace(/^=\s*/, ''); if (t && !res.classList.contains('bad')) { target.value += (target.value && !/\s$/.test(target.value) ? ' ' : '') + t; target.dispatchEvent(new Event('input')); } } };
  }

  return { evaluate, mount, setDegrees: d => { degrees = d; } };
})();
