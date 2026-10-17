window.Vocalis = window.Vocalis || {};

window.Vocalis.recorder = (() => {
  const $ = id => document.getElementById(id);
  const cv = $('wave'), ctx = cv.getContext('2d');
  let audioCtx, analyser, stream, recorder, chunks = [], state = 'idle', fake = false;
  let t0 = 0, acc = 0, pauses = 0, lvlSum = 0, lvlN = 0;
  let onStart = () => {}, onSubmit = () => {};
  const last = new Uint8Array(48);

  function size(){
    const r = cv.getBoundingClientRect(), d = devicePixelRatio || 1;
    cv.width = r.width*d;
    cv.height = r.height*d;
  }
  window.addEventListener('resize', size);
  size();

  const elapsed = () => acc + (state === 'rec' ? performance.now() - t0 : 0);

  function draw(){
    const w = cv.width, h = cv.height, bars = 48, gap = w/bars;
    ctx.clearRect(0,0,w,h);
    if(state === 'rec'){
      if(analyser && !fake){
        const buf = new Uint8Array(analyser.frequencyBinCount);
        analyser.getByteFrequencyData(buf);
        for(let i=0;i<bars;i++) last[i] = buf[Math.floor(i*buf.length*0.6/bars)];
        lvlSum += last.reduce((a,b) => a+b, 0)/bars/255;
        lvlN++;
      } else {
        const t = performance.now()/1000;
        for(let i=0;i<bars;i++) last[i] = 70 + 90*Math.abs(Math.sin(t*3 + i*.5)*Math.sin(t*1.3 + i*.2));
      }
    }
    for(let i=0;i<bars;i++){
      const v = state !== 'idle' ? Math.max(.06, last[i]/255) : .05 + .02*Math.sin(i);
      const bh = v*h*.9, x = i*gap + gap*.2;
      ctx.fillStyle = state === 'rec' ? (i%3 ? '#8f2a3f' : '#e9dcc3') : state === 'paused' ? '#7a6b5a' : '#3a2428';
      ctx.beginPath();
      ctx.roundRect(x, (h-bh)/2, gap*.6, bh, gap*.3);
      ctx.fill();
    }
    requestAnimationFrame(draw);
  }

  function ui(){
    const idle = state === 'idle', rec = state === 'rec';
    $('mic').classList.toggle('rec', rec);
    $('mic').setAttribute('aria-pressed', rec);
    $('mic').setAttribute('aria-label', idle ? 'Start recording' : rec ? 'Pause recording' : 'Resume recording');
    $('pause').disabled = idle;
    $('pause').textContent = state === 'paused' ? 'Resume' : 'Pause';
    $('submit').disabled = idle;
    $('status').textContent = idle ? 'Tap the microphone and speak.' : rec ? 'Recording… use Pause to hold, Submit to finish.' : 'Paused. Tap Resume to continue.';
    if(!idle && fake) $('status').textContent = 'Microphone unavailable here. Showing a preview of the waveform.';
  }

  async function start(){
    acc = 0; pauses = 0; lvlSum = 0; lvlN = 0; chunks = []; recorder = null; fake = false;
    onStart();
    try{
      stream = await navigator.mediaDevices.getUserMedia({audio:true});
      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      analyser = audioCtx.createAnalyser();
      analyser.fftSize = 256;
      analyser.smoothingTimeConstant = .75;
      audioCtx.createMediaStreamSource(stream).connect(analyser);
      if(window.MediaRecorder){
        recorder = new MediaRecorder(stream);
        recorder.ondataavailable = e => { if(e.data.size) chunks.push(e.data); };
        recorder.start();
      }
    }catch(err){
      fake = true;
    }
    t0 = performance.now();
    state = 'rec';
    ui();
  }

  function togglePause(){
    if(state === 'rec'){
      acc += performance.now() - t0;
      state = 'paused';
      pauses++;
      if(recorder && recorder.state === 'recording') recorder.pause();
      if(audioCtx) audioCtx.suspend();
    } else if(state === 'paused'){
      t0 = performance.now();
      state = 'rec';
      if(recorder && recorder.state === 'paused') recorder.resume();
      if(audioCtx) audioCtx.resume();
    }
    ui();
  }

  function submit(){
    if(state === 'idle') return;
    const report = {
      len: elapsed(),
      pauses,
      averageLevel: lvlN ? lvlSum/lvlN : null
    };
    state = 'idle';
    const finish = () => {
      report.audioBlob = chunks.length
        ? new Blob(chunks, {type: (recorder && recorder.mimeType) || 'audio/webm'})
        : null;
      onSubmit(report);
    };
    if(recorder && recorder.state !== 'inactive'){
      recorder.onstop = finish;
      recorder.stop();
    } else {
      finish();
    }
    if(stream) stream.getTracks().forEach(t => t.stop());
    if(audioCtx) audioCtx.close();
    analyser = null;
    ui();
    $('status').textContent = 'Recording submitted. Your report is ready.';
  }

  function init(callbacks){
    onStart = callbacks.onStart;
    onSubmit = callbacks.onSubmit;
    draw();
    $('mic').onclick = () => state === 'idle' ? start() : togglePause();
    $('pause').onclick = togglePause;
    $('submit').onclick = submit;
  }

  return {init};
})();
