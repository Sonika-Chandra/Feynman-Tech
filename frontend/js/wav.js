/* Converts a browser recording (usually WebM) to 16 kHz mono WAV, a format Gemini accepts for sure. */
window.Vocalis = window.Vocalis || {};

window.Vocalis.wav = (() => {
  const RATE = 16000;

  function encode(samples, rate) {
    const buf = new ArrayBuffer(44 + samples.length * 2), v = new DataView(buf);
    const text = (o, s) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); };
    text(0, 'RIFF'); v.setUint32(4, 36 + samples.length * 2, true); text(8, 'WAVE');
    text(12, 'fmt '); v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
    v.setUint32(24, rate, true); v.setUint32(28, rate * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true);
    text(36, 'data'); v.setUint32(40, samples.length * 2, true);
    for (let i = 0; i < samples.length; i++) {
      const s = Math.max(-1, Math.min(1, samples[i]));
      v.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
    }
    return new Blob([buf], { type: 'audio/wav' });
  }

  async function fromBlob(blob) {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    const ac = new Ctx();
    try {
      const decoded = await ac.decodeAudioData(await blob.arrayBuffer());
      const off = new OfflineAudioContext(1, Math.max(1, Math.ceil(decoded.duration * RATE)), RATE);
      const src = off.createBufferSource();
      src.buffer = decoded;
      src.connect(off.destination);
      src.start();
      const rendered = await off.startRendering();
      return encode(rendered.getChannelData(0), RATE);
    } finally {
      ac.close();
    }
  }

  return { encode, fromBlob };
})();
