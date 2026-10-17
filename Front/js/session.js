const TEMPERATURE = 0; // locked: pass this value to your model API
const $ = id => document.getElementById(id);
let text = "", topics = [], sel = null;

/* Upload */
const drop = $('drop'), fileIn = $('file');
async function readFile(f){
  const ext = f.name.split('.').pop().toLowerCase();
  if(ext === 'docx'){
    return (await mammoth.extractRawText({arrayBuffer: await f.arrayBuffer()})).value;
  }
  if(ext === 'pdf'){
    pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
    const pdf = await pdfjsLib.getDocument({data: await f.arrayBuffer()}).promise;
    let out = '';
    for(let p = 1; p <= pdf.numPages; p++){
      const c = await (await pdf.getPage(p)).getTextContent();
      out += c.items.map(i => i.str).join(' ') + '\n\n';
    }
    return out;
  }
  if(ext === 'doc') throw new Error('Old .doc files are not supported. Save it as .docx and upload it again.');
  return await f.text();
}
async function load(f){
  if(!f) return;
  const info = f.name + " (" + Math.max(1, Math.round(f.size/1024)) + " KB)";
  $('fname').textContent = info;
  try{ text = await readFile(f); build(); }
  catch(err){ text = ''; $('fname').textContent = info + '. ' + (/\.doc/.test(err.message) ? err.message : 'This file could not be read.'); }
}
fileIn.onchange = e => load(e.target.files[0]);
['dragover','dragenter'].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.add('over'); }));
['dragleave','drop'].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.remove('over'); }));
drop.addEventListener('drop', e => { fileIn.files = e.dataTransfer.files; load(e.dataTransfer.files[0]); });

/* Subtopic extraction (placeholder: swap with your model call, temperature = TEMPERATURE) */
function extract(t){
  const lines = t.split(/\r?\n/), out = [];
  lines.forEach((ln, i) => {
    const s = ln.trim();
    const isHead = /^#{1,4}\s+/.test(s) || /^(\d+[\.\)]|[IVX]+\.)\s+\S/.test(s) ||
      (s.length > 3 && s.length < 70 && !/[.,;]$/.test(s) && /^[A-Z]/.test(s) && lines[i+1] !== undefined && lines[i+1].trim() === "" && s.split(" ").length < 9);
    if(isHead){
      const body = lines.slice(i+1, i+8).join(" ").replace(/\s+/g," ").trim();
      out.push({title: s.replace(/^#{1,4}\s+/,""), body});
    }
  });
  if(out.length) return out;
  const stop = new Set("the and for that with this from are was were have has not but you your they their will can its into than then them which about more also such been when what who how".split(" "));
  const freq = {};
  (t.toLowerCase().match(/[a-z]{4,}/g) || []).forEach(w => { if(!stop.has(w)) freq[w] = (freq[w]||0)+1; });
  const sents = t.split(/(?<=[.!?])\s+/);
  return Object.keys(freq).sort((a,b) => freq[b]-freq[a]).slice(0,8).map(w => ({
    title: w[0].toUpperCase()+w.slice(1),
    body: sents.filter(s => s.toLowerCase().includes(w)).slice(0,2).join(" ")
  }));
}
function build(){
  sel = null; topics = extract(text);
  const list = $('ddl'); list.innerHTML = "";
  if(!topics.length){ list.innerHTML = '<li role="option" data-none>None</li>'; $('ddv').textContent = "None"; return; }
  topics.forEach((tp, i) => {
    const li = document.createElement('li');
    li.setAttribute('role','option'); li.textContent = tp.title;
    li.onclick = () => pick(i);
    list.appendChild(li);
  });
  
  $('ddv').textContent = "Choose subtopics";
  $('note').textContent = "The passage for the chosen subtopic appears here.";
};
function pick(i){
  sel = topics[i];
  $('ddv').textContent = topics[i].title;
  $('note').textContent = topics[i].body || "No passage found under this subtopic.";
  [...$('ddl').children].forEach((li,j) => li.setAttribute('aria-selected', j===i));
  setOpen(false);
}
function setOpen(v){ $('dd').classList.toggle('open', v); $('ddb').setAttribute('aria-expanded', v); }
$('ddb').onclick = () => setOpen(!$('dd').classList.contains('open'));
$('ddl').addEventListener('click', e => { if(e.target.hasAttribute('data-none')){ sel = null; $('ddv').textContent = "None"; $('note').textContent = "The passage for the chosen subtopic appears here."; setOpen(false); } });
document.addEventListener('click', e => { if(!$('dd').contains(e.target)) setOpen(false); });
document.addEventListener('keydown', e => { if(e.key === 'Escape') setOpen(false); });

const grid = document.querySelector('.grid');
let tab = 'say';
function layout(){ grid.classList.toggle('has-report', Vocalis.results.isVisible() && tab === 'say'); }
function setTab(t){
  tab = t; grid.dataset.tab = t;
  document.querySelectorAll('.nav .l').forEach(b => b.setAttribute('aria-pressed', b.dataset.tab === t));
  layout(); window.scrollTo({top: 0, behavior: 'smooth'});
}
document.querySelectorAll('.nav .l').forEach(b => b.onclick = () => setTab(b.dataset.tab));
function hideReport(){ Vocalis.results.hide(); layout(); }
$('again').onclick = () => { hideReport(); setTab('say'); };
Vocalis.recorder.init({
  onStart: hideReport,
  onSubmit: ({len, pauses, averageLevel, audioBlob}) => {
    const selectedFile = fileIn.files[0];
    Vocalis.results.show({
      len,
      pauses,
      averageLevel,
      audioBlob,
      documentName: selectedFile ? selectedFile.name : 'None uploaded',
      topic: sel ? sel.title : 'None selected',
      passage: sel && sel.body ? sel.body : 'Choose a subtopic before recording to see its passage here.'
    });
    layout();
  }
});
layout();
