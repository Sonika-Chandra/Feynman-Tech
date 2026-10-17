window.Vocalis = window.Vocalis || {};

window.Vocalis.results = (() => {
  const $ = id => document.getElementById(id);
  let blobUrl = null;

  function show({len, pauses, averageLevel, audioBlob, documentName, topic, passage}){
    if(blobUrl){
      URL.revokeObjectURL(blobUrl);
      blobUrl = null;
    }

    if(audioBlob){
      blobUrl = URL.createObjectURL(audioBlob);
      $('play').src = blobUrl;
      $('play').hidden = false;
    } else {
      $('play').removeAttribute('src');
      $('play').hidden = true;
    }

    const seconds = Math.round(len/1000);
    $('r-doc').textContent = documentName;
    $('r-topic').textContent = topic;
    $('r-len').textContent = Math.floor(seconds/60) + ':' + String(seconds%60).padStart(2,'0');
    $('r-pauses').textContent = pauses;
    $('r-lvl').textContent = averageLevel === null ? 'Not measured' : Math.round(averageLevel*100) + '% of maximum';
    $('r-pass').textContent = passage;
    $('report').hidden = false;
    $('report').scrollIntoView({behavior: 'smooth', block: 'nearest'});
  }

  function hide(){
    $('report').hidden = true;
  }

  function isVisible(){
    return !$('report').hidden;
  }

  return {show, hide, isVisible};
})();
