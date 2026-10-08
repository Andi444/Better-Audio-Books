'use strict';
const $=id=>document.getElementById(id);
const {words,chunk,boundaryAt}=BABCore;
const fragment=new URLSearchParams(location.hash.slice(1));
const token=fragment.get('token')||sessionStorage.getItem('bab-token')||'';
sessionStorage.setItem('bab-token',token);
let catalog=[],library=[],book=null,tokens=[],wordNodes=[],voice='female-01',gender='female',voiceMode='offline';
let backgroundVoices=true;
let position=0,selected=-1,state='idle',generation=0,previewGeneration=0,segment=null;
let fontSize=23,fontFamily='georgia',volume=.8,speed=1,follow=true,theme='light',editingId=null,saveTimer=null,settingsTimer=null;
const readerFonts={georgia:'Georgia, "Times New Roman", serif',segoe:'"Segoe UI", Arial, sans-serif',arial:'Arial, sans-serif',verdana:'Verdana, sans-serif',times:'"Times New Roman", serif',consolas:'Consolas, "Courier New", monospace'};
let lastSaved='',toastTimer=null,ready=false,saveChain=Promise.resolve(),restoreBusy=false;
const audio=new Audio(),preview=new Audio(),requests=new Map();
audio.preload='auto';audio.preservesPitch=true;

async function api(path,data){
  const response=await fetch(path,{method:data===undefined?'GET':'POST',headers:{'X-BAB-Token':token,'Content-Type':'application/json'},body:data===undefined?undefined:JSON.stringify(data)});
  let result;try{result=await response.json();}catch{throw new Error('BAB svarar inte. Starta programmet igen.');}
  if(!response.ok)throw new Error(result.error||'Något gick fel. Försök igen.');
  return result;
}
function toast(message){clearTimeout(toastTimer);$('toast').textContent=message;$('toast').hidden=false;toastTimer=setTimeout(()=>$('toast').hidden=true,6500);}
function report(error){toast(error.message||String(error));}
function setStatus(message){$('status').textContent=message;}
function setState(next,message){state=next;document.body.classList.toggle('playing',next==='playing');document.body.classList.toggle('loading',next==='loading');$('play').textContent=next==='playing'?'Ⅱ':next==='loading'?'■':'▶';$('play').setAttribute('aria-label',next==='playing'?'Pausa uppläsning':next==='loading'?'Avbryt förberedelse':'Starta uppläsning');if(message)setStatus(message);}
function selectedVoice(){return catalog.find(v=>v.id===voice)||catalog[0];}
function stopPreview(){previewGeneration++;preview.pause();preview.removeAttribute('src');$('previewVoice').textContent='▷ Provlyssna';$('previewVoice').disabled=false;}
function stop(message){generation++;audio.pause();audio.removeAttribute('src');audio.load();segment=null;stopPreview();setState(book?'paused':'idle',message);}
function pause(){
  if(state==='loading'){stop('Pausad. Tryck på spela för att fortsätta.');}
  else{audio.pause();setState('paused','Pausad · din plats är sparad');}
  savePosition();
}
function updateProgress(){
  const percent=tokens.length?Math.round(position/tokens.length*100):0;
  $('progressText').textContent=percent+' %';$('progress').max=Math.max(0,tokens.length-1);$('progress').value=Math.min(position,Math.max(0,tokens.length-1));
  $('wordProgress').textContent=`${position.toLocaleString('sv-SE')} / ${tokens.length.toLocaleString('sv-SE')} ord`;
  $('progress').setAttribute('aria-valuetext',`${percent} procent, ord ${position} av ${tokens.length}`);
}
let highlighted=-1;
function mark(index,scroll=false){
  index=Math.max(0,Math.min(index,tokens.length-1));
  if(highlighted!==index){wordNodes[highlighted]?.classList.remove('current');highlighted=index;wordNodes[index]?.classList.add('current');}
  if(scroll&&follow&&wordNodes[index]){
    const rect=wordNodes[index].getBoundingClientRect();
    const viewport=$('reader').getBoundingClientRect();
    if(rect.top<viewport.top+18||rect.bottom>viewport.bottom-24)$('reader').scrollTop+=rect.top-viewport.top-viewport.height/2;
  }
}
function setPosition(index,scroll=false){position=Math.max(0,Math.min(index,tokens.length));mark(position,scroll);updateProgress();}
function positionSnapshot(){return book?{id:book.id,position,voice}:null;}
function savePosition(){
  const snapshot=positionSnapshot();if(!snapshot)return Promise.resolve();
  const signature=JSON.stringify(snapshot);if(signature===lastSaved)return saveChain;
  lastSaved=signature;
  saveChain=saveChain.catch(()=>{}).then(()=>api('/api/position',snapshot)).then(()=>{
    if(book?.id===snapshot.id){$('saveStatus').textContent='Läsposition sparad';book.position=snapshot.position;book.voice=snapshot.voice;}
    const item=library.find(b=>b.id===snapshot.id);if(item){item.position=snapshot.position;item.voice=snapshot.voice;}
  }).catch(error=>{lastSaved='';$('saveStatus').textContent='Kunde inte spara';report(error);});
  return saveChain;
}
function settingsSnapshot(){return {fontSize,fontFamily,volume,theme,speed,follow,voiceMode,lastBook:book?.id||null};}
function saveSettings(){clearTimeout(settingsTimer);settingsTimer=setTimeout(()=>api('/api/settings',settingsSnapshot()).catch(report),300);}
function applySettings(settings){
  voiceMode=settings.voiceMode==='online'?'online':'offline';voice=voiceMode==='online'?'online-female-01':'female-01';
  fontSize=Math.max(17,Math.min(35,Number(settings.fontSize)||23));speed=[.65,.8,1,1.15,1.3,1.5,1.75,2].includes(Number(settings.speed))?Number(settings.speed):1;
  volume=Number.isFinite(settings.volume)?Math.max(0,Math.min(1,settings.volume)):.8;setVolume(volume);
  follow=settings.follow!==false;theme=settings.theme==='dark'?'dark':'light';
  fontFamily=Object.hasOwn(readerFonts,settings.fontFamily)?settings.fontFamily:'georgia';
  document.documentElement.style.setProperty('--reader-font',readerFonts[fontFamily]);$('fontFamily').value=fontFamily;
  document.documentElement.style.setProperty('--reader-size',fontSize+'px');document.body.classList.toggle('dark',theme==='dark');$('speed').value=String(speed);$('follow').checked=follow;audio.playbackRate=speed;
}
function renderLibrary(){
  $('bookCount').textContent=library.length;const list=$('bookList');list.replaceChildren();
  const query=$('bookSearch').value.trim().toLocaleLowerCase('sv');
  const matches=library.filter(b=>b.title.toLocaleLowerCase('sv').includes(query));
  if(!matches.length){const p=document.createElement('p');p.className='empty-library';p.textContent=library.length?'Ingen bok matchar sökningen.':'Dina böcker samlas här.';list.append(p);}
  for(const item of matches){const button=document.createElement('button');button.className='library-item'+(book?.id===item.id?' active':'');button.setAttribute('aria-pressed',String(book?.id===item.id));const title=document.createElement('strong');title.textContent=item.title;const meta=document.createElement('small');meta.textContent=item.position?`Fortsätt från ord ${item.position.toLocaleString('sv-SE')}`:'Redo att läsa';button.append(title,meta);button.onclick=()=>openBook(item.id).catch(report);list.append(button);}
}
function setVoiceMode(mode){
  if(mode===voiceMode)return;
  const resume=state==='playing'||state==='loading';
  const previous=selectedVoice();stop('Röstläge ändrat · redo att läsa');voiceMode=mode;
  voice=catalog.find(v=>v.mode===mode&&v.gender===previous.gender&&v.style===previous.style).id;
  gender=previous.gender;requests.clear();renderVoices();savePosition();saveSettings();
  if(resume)startFrom(position);else warmPosition();
}
function renderVoices(){
  const online=voiceMode==='online';
  for(const mode of ['offline','online']){const button=$(mode+'Mode');button.classList.toggle('active',mode===voiceMode);button.setAttribute('aria-pressed',String(mode===voiceMode));}
  $('modeStatus').textContent=online?'Onlineröster · internet behövs':'Offlineröster · utan internet';
  $('modeDescription').textContent=online?'Sofie & Mattias · internet behövs.':'Alma & NST · fungerar utan internet.';
  $('voiceInfo').textContent=online?'20 klangvarianter av Sofie och 20 av Mattias. Samma onlineröster som tidigare.':'20 klangvarianter av Alma och 20 av NST. Sammanhängande uttal och varsammare klangvariationer.';
  $('voicePrivacy').textContent=online?'Avsnitten du lyssnar på skickas till Microsofts rösttjänst. Ljudet sparas på datorn. Välj Offline för att läsa utan internet.':'Texten stannar på datorn. Röster och ljud sparas lokalt. Nya avsnitt kan ta en kort stund att skapa.';
  const list=$('voiceList');list.replaceChildren();
  for(const v of catalog.filter(v=>v.gender===gender&&v.mode===voiceMode)){
    const button=document.createElement('button');button.className='voice-option'+(v.id===voice?' active':'');button.setAttribute('aria-pressed',String(v.id===voice));button.setAttribute('aria-label',v.name);
    const dot=document.createElement('span');dot.className='voice-dot';dot.textContent=v.base[0];const label=document.createElement('span');const name=document.createElement('strong');name.textContent=v.style;const small=document.createElement('small');small.textContent=`${v.base} · Svenska`;label.append(name,small);const check=document.createElement('span');check.className='check';check.textContent=v.id===voice?'✓':'';button.append(dot,label,check);
    button.onclick=()=>{if(voice!==v.id){const resume=state==='playing'||state==='loading';stop('Röst vald · redo att läsa');voice=v.id;savePosition();if(resume)startFrom(position);else warmPosition();}renderVoices();};list.append(button);
  }
  $('femaleTab').classList.toggle('active',gender==='female');$('maleTab').classList.toggle('active',gender==='male');$('femaleTab').setAttribute('aria-pressed',String(gender==='female'));$('maleTab').setAttribute('aria-pressed',String(gender==='male'));$('chosenVoice').textContent=selectedVoice()?.name||'';
}
function renderBook(){
  const has=!!book;$('emptyState').hidden=has;$('reader').hidden=!has;$('editBook').hidden=!has;$('deleteBook').hidden=!has;$('play').disabled=!has;$('progress').disabled=!has;$('back').disabled=!has;$('forward').disabled=!has;
  $('bookTitle').textContent=book?.title||'En stund för orden.';$('playingTitle').textContent=book?.title||'Din nästa läsupplevelse';$('bookKicker').textContent=has?'DIN BOK · DITT TEMPO':'VÄLKOMMEN TILL BAB';$('bookMeta').textContent=has?`${tokens.length.toLocaleString('sv-SE')} ord · ca ${Math.max(1,Math.round(tokens.length/150/speed))} min · Svenska`:'Lägg till din text och låt berättelsen ta plats.';
  const reader=$('reader');reader.replaceChildren();wordNodes=[];highlighted=-1;
  if(has){
    const fragment=document.createDocumentFragment();let offset=0,block=null,blockStart=0;
    tokens.forEach((word,i)=>{
      const space=book.text.slice(offset,word.offset);
      if(block)block.append(document.createTextNode(space));
      // Isolate layout work and let Chromium defer off-screen blocks. Every word
      // stays in the document, preserving selection, find, and click-to-read.
      if(!block||(i-blockStart>=120&&space.includes('\n'))||i-blockStart>=240){
        block=document.createElement('div');block.className='reader-block';fragment.append(block);blockStart=i;
      }
      if(i===0)block.append(document.createTextNode(space));
      const span=document.createElement('span');span.className='word';span.dataset.word=String(i);span.textContent=word.text;wordNodes.push(span);block.append(span);offset=word.end;
    });
    if(block)block.append(document.createTextNode(book.text.slice(offset)));
    reader.append(fragment);reader.scrollTop=0;mark(position);
  }
  updateProgress();renderLibrary();
}
let openGeneration=0;
async function openBook(id){
  const request=++openGeneration;await savePosition();stop('Öppnar boken…');closeSelection();
  const result=await api('/api/book/'+encodeURIComponent(id));if(request!==openGeneration)return;
  book=result;tokens=words(book.text);position=Math.min(book.position,tokens.length);voice=catalog.some(v=>v.id===book.voice)?book.voice:'female-01';gender=selectedVoice().gender;voiceMode=selectedVoice().mode;requests.clear();lastSaved='';renderBook();renderVoices();document.body.classList.remove('library-open');warmPosition();setState('paused',position>=tokens.length?'Boken är färdigläst · spela för att börja om':'Redo när du är · tryck på spela');saveSettings();
}
let parts=[],partsBook=null;
function partAt(index){
  if(!book||index>=tokens.length)return null;
  if(partsBook!==book){parts=[];let start=0;while(start<tokens.length){const part=chunk(book.text,tokens,start);parts.push(part);start=part.end;}partsBook=book;}
  return parts.find(part=>part.start<=index&&index<part.end)||null;
}
function warmPosition(){if(!backgroundVoices||!book||voiceMode!=='offline')return;const part=partAt(Math.min(position,tokens.length-1));if(!part)return;speechFor(part,voice).catch(()=>{});speechFor(part,voice.startsWith('male')?'female-01':'male-01').catch(()=>{});}
function speechFor(part,chosen){
  const key=chosen+'\n'+part.text;
  if(!requests.has(key)){
    if(requests.size>40)requests.delete(requests.keys().next().value);
    const promise=api('/api/speak',{text:part.text,voice:chosen});requests.set(key,promise);
    promise.catch(()=>{if(requests.get(key)===promise)requests.delete(key);});
  }
  return requests.get(key);
}
async function startFrom(index){
  if(!book||!tokens.length)return;
  stopPreview();generation++;const currentGeneration=generation;audio.pause();segment=null;closeSelection();
  if(index>=tokens.length)index=0;
  setPosition(index,true);savePosition();setState('loading',voiceMode==='online'?'Hämtar onlineröst…':'Startar lokal uppläsning…');
  const chosen=voice,part=partAt(index),sourceBook=book;
  try{
    const result=await speechFor(part,chosen);if(currentGeneration!==generation||book!==sourceBook)return;
    segment={...part,...result,seekWord:index};audio.src=result.audio+'?token='+encodeURIComponent(token);audio.playbackRate=speed;
    await new Promise((resolve,reject)=>{if(audio.readyState>=1)return resolve();audio.addEventListener('loadedmetadata',resolve,{once:true});audio.addEventListener('error',reject,{once:true});});
    if(currentGeneration!==generation)return;const begin=result.timings.find(t=>t.word>=index-part.start);audio.currentTime=begin?begin.start+.001:0;
    await audio.play();if(currentGeneration!==generation)return;
    setState('playing',selectedVoice().name+' · läser');
    const next=partAt(part.end);if(next){speechFor(next,chosen).catch(()=>{});if(backgroundVoices&&voiceMode==='offline')speechFor(next,chosen.startsWith('male')?'female-01':'male-01').catch(()=>{});}
  }catch(error){if(currentGeneration!==generation)return;segment=null;setState('paused','Kunde inte starta · tryck på spela för att försöka igen');report(error);}
}
async function togglePlay(){
  if(!book)return;
  stopPreview();
  if(state==='playing'||state==='loading'){pause();return;}
  if(segment&&audio.src&&!audio.ended){
    try{await audio.play();setState('playing',selectedVoice().name+' · läser');}catch(error){report(error);}
  }else await startFrom(position);
}
audio.addEventListener('ended',()=>{
  if(!segment||state!=='playing')return;const next=segment.end;
  if(next>=tokens.length){setPosition(tokens.length);segment=null;setState('finished','Färdigläst · tack för den här stunden');savePosition();renderLibrary();}
  else startFrom(next);
});
audio.addEventListener('error',()=>{if(state==='playing'){pause();segment=null;setStatus('Ljudet kunde inte spelas. Tryck på spela för att försöka igen.');}});
function animate(){
  if(state==='playing'&&segment){const boundary=boundaryAt(segment.timings,audio.currentTime);if(boundary){const index=Math.max(segment.seekWord||0,segment.start+boundary.word);if(index!==position){setPosition(index,true);}}}
  setTimeout(animate,state==='playing'?60:500);
}
async function previewVoice(){
  if(!preview.paused||$('previewVoice').disabled){stopPreview();setStatus(book?'Pausad · tryck på spela för att fortsätta':'Välj en bok för att börja');return;}
  if(state==='playing'||state==='loading')pause();
  stopPreview();const id=++previewGeneration,chosen=voice;
  $('previewVoice').disabled=true;$('previewVoice').textContent='Startar…';setStatus(voiceMode==='online'?'Hämtar röstprov online…':'Startar lokalt röstprov…');
  try{const result=await api('/api/speak',{voice:chosen,text:'Välkommen till Better Audio Books. Slå dig ner en stund och följ orden i din egen takt. Här får varje berättelse en röst.'});if(id!==previewGeneration)return;preview.src=result.audio+'?token='+encodeURIComponent(token);preview.playbackRate=speed;await preview.play();if(id!==previewGeneration)return;$('previewVoice').disabled=false;$('previewVoice').textContent='■ Stoppa röstprov';setStatus('Provlyssnar · '+selectedVoice().name);}
  catch(error){if(id!==previewGeneration)return;report(error);stopPreview();setStatus('Kunde inte spela röstprovet · försök igen');}
}
preview.addEventListener('ended',()=>{stopPreview();setStatus(book?'Pausad · tryck på spela för att fortsätta':'Välj en bok för att börja');});
function closeSelection(){wordNodes[selected]?.classList.remove('selected');selected=-1;$('selection').hidden=true;}
function placeSelection(){
  const target=wordNodes[selected];if(!target)return;
  const rect=target.getBoundingClientRect(),popup=$('selection'),width=popup.offsetWidth;
  popup.style.left=Math.max(12,Math.min(rect.left,innerWidth-width-12))+'px';popup.style.top=Math.max(10,Math.min(rect.bottom+10,innerHeight-180))+'px';
}
function selectWord(index,target){
  if(state==='playing'||state==='loading')pause();stopPreview();closeSelection();selected=index;target.classList.add('selected');$('selectedWord').textContent=tokens[index].text;$('selection').hidden=false;
  placeSelection();$('readHere').focus({preventScroll:true});
}
$('reader').addEventListener('click',event=>{const target=event.target.closest('.word');if(target)selectWord(Number(target.dataset.word),target);});
$('reader').addEventListener('keydown',event=>{if(event.key==='Enter'&&tokens.length){event.preventDefault();selectWord(Math.min(position,tokens.length-1),wordNodes[Math.min(position,tokens.length-1)]);}});
$('readHere').onclick=()=>{const index=selected;closeSelection();if(index>=0)startFrom(index);};
$('closeSelection').onclick=closeSelection;
$('reader').addEventListener('scroll',()=>{if(!$('selection').hidden)placeSelection();},{passive:true});
window.addEventListener('resize',placeSelection);window.addEventListener('scroll',()=>{if(!$('selection').hidden)placeSelection();},{passive:true});
document.addEventListener('click',event=>{if(!event.target.closest('#selection')&&!event.target.closest('.word'))closeSelection();});
document.addEventListener('keydown',event=>{if(event.key==='Escape')closeSelection();if(event.code==='Space'&&!event.target.closest('input,textarea,select,button,dialog')&&book){event.preventDefault();togglePlay();}});

function openEditor(edit=false){
  largePasteHistory=null;
  if(state==='playing'||state==='loading')pause();stopPreview();editingId=edit?book?.id:null;$('editorTitle').textContent=edit?'Redigera boken':'Lägg till en bok';$('titleInput').value=edit?book.title:'';$('textInput').value=edit?book.text:'';updateTextCount();$('editor').showModal();$('titleInput').focus();
}
function updateTextCount(){const pattern=/\S+/gu,text=$('textInput').value;let count=0;while(pattern.exec(text))count++;$('textCount').textContent=count.toLocaleString('sv-SE')+' ord';}
let countTimer;$('textInput').oninput=()=>{clearTimeout(countTimer);countTimer=setTimeout(updateTextCount,200);};
let largePasteHistory=null;
$('textInput').addEventListener('paste',event=>{
  const incoming=event.clipboardData?.getData('text/plain');
  if(!incoming||incoming.length<4096)return;
  const field=$('textInput'),before=field.value,start=field.selectionStart,end=field.selectionEnd;
  const available=field.maxLength-before.length+end-start;
  const text=incoming.replace(/\r\n?/g,'\n').slice(0,Math.max(0,available));
  event.preventDefault();
  // Native rich editing/undo processing is disproportionately slow for a whole
  // book. Replace once, then retain a reversible paste without touching content.
  field.setRangeText(text,start,end,'end');
  largePasteHistory={before,after:field.value,start,end,caret:field.selectionStart};
  field.dispatchEvent(new Event('input',{bubbles:true}));
});
$('textInput').addEventListener('keydown',event=>{
  if(!(event.ctrlKey||event.metaKey)||event.altKey||!largePasteHistory)return;
  const redo=event.key.toLowerCase()==='y'||(event.key.toLowerCase()==='z'&&event.shiftKey);
  const undo=event.key.toLowerCase()==='z'&&!event.shiftKey;
  const field=$('textInput'),h=largePasteHistory;
  if((undo&&field.value===h.after)||(redo&&field.value===h.before)){
    event.preventDefault();field.value=undo?h.before:h.after;
    field.setSelectionRange(undo?h.start:h.caret,undo?h.end:h.caret);
    field.dispatchEvent(new Event('input',{bubbles:true}));
  }
});
$('newBook').onclick=() =>openEditor();$('emptyNew').onclick=()=>openEditor();$('editBook').onclick=()=>openEditor(true);
$('closeEditor').onclick=$('cancelEditor').onclick=()=>$('editor').close();
$('importText').onclick=()=>$('textFile').click();
$('textFile').onchange=async()=>{const file=$('textFile').files[0];if(!file)return;try{if(file.size>4_000_000)throw new Error('Textfilen är för stor. Dela upp boken i mindre delar.');const bytes=new Uint8Array(await file.arrayBuffer());const utf16le=bytes[0]===255&&bytes[1]===254,utf16be=bytes[0]===254&&bytes[1]===255;let text;try{text=new TextDecoder(utf16le?'utf-16le':utf16be?'utf-16be':'utf-8',{fatal:true}).decode(bytes);}catch{text=new TextDecoder('windows-1252').decode(bytes);}if(text.length>1_000_000)throw new Error('Texten får innehålla högst 1 000 000 tecken.');$('textInput').value=text;largePasteHistory=null;if(!$('titleInput').value)$('titleInput').value=file.name.replace(/\.txt$/i,'').slice(0,160);updateTextCount();}catch(error){report(error);}finally{$('textFile').value='';}};
$('bookForm').onsubmit=async event=>{
  event.preventDefault();$('saveBook').disabled=true;
  try{await savePosition();const text=$('textInput').value;const unchanged=editingId&&book?.id===editingId&&text===book.text;const result=await api('/api/book',{id:editingId,title:$('titleInput').value,text,voice,position:unchanged?position:0});$('editor').close();await refreshLibrary();await openBook(result.id);toast('Boken är sparad i ditt bibliotek.');}
  catch(error){report(error);}finally{$('saveBook').disabled=false;}
};
async function refreshLibrary(){const data=await api('/api/bootstrap');library=data.books;renderLibrary();}
function confirmAction(title,text,label){return new Promise(resolve=>{$('confirmTitle').textContent=title;$('confirmText').textContent=text;$('confirmYes').textContent=label;$('confirmDialog').showModal();const finish=value=>{$('confirmDialog').close();resolve(value);};$('confirmYes').onclick=()=>finish(true);$('confirmCancel').onclick=()=>finish(false);$('confirmDialog').oncancel=()=>resolve(false);});}
$('deleteBook').onclick=async()=>{if(!book)return;const id=book.id;if(state==='playing'||state==='loading')pause();if(!await confirmAction('Ta bort boken?',`”${book.title}” tas bort från biblioteket. Detta går inte att ångra.`,'Ta bort'))return;try{await savePosition();stop();await api('/api/delete',{id});book=null;tokens=[];position=0;closeSelection();await refreshLibrary();renderBook();saveSettings();setState('idle','Välj en bok för att börja');}catch(error){report(error);}};
$('bookSearch').oninput=renderLibrary;
$('femaleTab').onclick=()=>{gender='female';renderVoices();};$('maleTab').onclick=()=>{gender='male';renderVoices();};$('previewVoice').onclick=previewVoice;
$('play').onclick=togglePlay;
function seek(index){const resume=state==='playing'||state==='loading';stop('Läsposition ändrad · tryck på spela');setPosition(index,true);savePosition();if(resume)startFrom(position);}
$('back').onclick=()=>{if(book)seek(Math.max(0,position-15));};$('forward').onclick=()=>{if(book)seek(Math.min(tokens.length-1,position+15));};$('progress').onchange=()=>seek(Number($('progress').value));
$('speed').onchange=()=>{speed=Number($('speed').value);audio.playbackRate=speed;preview.playbackRate=speed;saveSettings();if(book)$('bookMeta').textContent=`${tokens.length.toLocaleString('sv-SE')} ord · ca ${Math.max(1,Math.round(tokens.length/150/speed))} min · Svenska`;};
function setVolume(value){volume=value;audio.volume=value;preview.volume=value;$('volume').value=String(Math.round(value*100));$('volumeValue').textContent=Math.round(value*100)+' %';}
$('volume').oninput=()=>{setVolume(Number($('volume').value)/100);saveSettings();};
$('offlineMode').onclick=()=>setVoiceMode('offline');
$('onlineMode').onclick=()=>setVoiceMode('online');
$('libraryToggle').onclick=()=>{document.body.classList.toggle('library-open');document.body.classList.remove('voices-open');};
$('voicesToggle').onclick=()=>{document.body.classList.toggle('voices-open');document.body.classList.remove('library-open');};
$('follow').onchange=()=>{follow=$('follow').checked;saveSettings();};
$('fontFamily').onchange=()=>{fontFamily=$('fontFamily').value;document.documentElement.style.setProperty('--reader-font',readerFonts[fontFamily]);placeSelection();saveSettings();};
$('desktopShortcut').onclick=async()=>{const button=$('desktopShortcut');button.disabled=true;button.textContent='Skapar genväg…';try{await api('/api/shortcut',{});toast('BAB finns nu som en genväg på skrivbordet.');}catch(error){report(error);}finally{button.disabled=false;button.textContent='Skapa skrivbordsgenväg ↗';}};
function resizeText(delta){fontSize=Math.max(17,Math.min(35,fontSize+delta));document.documentElement.style.setProperty('--reader-size',fontSize+'px');saveSettings();}
$('smaller').onclick=()=>resizeText(-2);$('larger').onclick=()=>resizeText(2);$('theme').onclick=()=>{theme=theme==='light'?'dark':'light';document.body.classList.toggle('dark',theme==='dark');saveSettings();};
$('backup').onclick=async()=>{try{await savePosition();const all=[];for(const item of library)all.push(await api('/api/book/'+item.id));const blob=new Blob([JSON.stringify({app:'BAB',version:1,books:all},null,2)],{type:'application/json'});const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='BAB-bibliotek-'+new Date().toISOString().slice(0,10)+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);toast('Säkerhetskopian innehåller dina texter och läspositioner.');}catch(error){report(error);}};
$('restore').onclick=()=>$('backupFile').click();
$('backupFile').onchange=async()=>{
  const file=$('backupFile').files[0];if(!file||restoreBusy)return;restoreBusy=true;
  try{if(file.size>50_000_000)throw new Error('Säkerhetskopian är för stor.');const data=JSON.parse(await file.text());if(data.app!=='BAB'||data.version!==1||!Array.isArray(data.books)||data.books.length>200)throw new Error('Välj en giltig BAB-säkerhetskopia med högst 200 böcker.');
    for(const item of data.books){if(typeof item.title!=='string'||typeof item.text!=='string'||!item.title.trim()||item.title.length>160||!item.text.trim()||item.text.length>1_000_000)throw new Error('Säkerhetskopian innehåller en ogiltig bok.');}
    let count=0;for(const item of data.books){await api('/api/book',{title:item.title,text:item.text,position:Number(item.position)||0,voice:catalog.some(v=>v.id===item.voice)?item.voice:'female-01'});count++;}await refreshLibrary();toast(`${count} böcker har lagts till. Befintliga böcker finns kvar.`);
  }catch(error){await refreshLibrary().catch(()=>{});report(error);}finally{restoreBusy=false;$('backupFile').value='';}
};
const demoText=`Det lilla biblioteket vid havet\n\nDet var en sådan morgon då havet nästan såg ut att stå stilla. Nora hade gått längs strandvägen med händerna i fickorna och en tanke som ännu inte ville bli färdig. Hon behövde ingen brådska i dag. Bara någonstans att sitta och något att läsa.\n\nPå hörnet låg ett litet bibliotek. Dörren var grön och hade en mässingsklocka som klingade till när hon öppnade den. Innanför väntade doften av papper, trä och nybryggt kaffe.\n\n”Du får slå dig ner var du vill”, sade mannen bakom disken. ”Den bästa platsen är den där du glömmer att titta på klockan.”\n\nNora log. Hon valde en fåtölj vid fönstret och tog upp boken som låg på det runda bordet. På första sidan stod en enda mening: Varje berättelse börjar med att någon stannar upp och lyssnar.\n\nHon läste den en gång till. Utanför gick en kvinna förbi med en röd halsduk. En mås landade på kajen. Allt det vanliga fortsatte, men inne i rummet hade tiden fått en annan rytm.\n\nNora vände blad. Hon visste ännu inte vart berättelsen skulle föra henne. Det gjorde ingenting. Just nu räckte det att följa ett ord i taget.\n\nProva själv\n\nKlicka på valfritt ord i den här texten och välj Läs härifrån. Rösten börjar på den plats du valt. Du kan pausa, byta klangvariant eller ändra hastigheten utan att förlora din läsposition.\n\nNär du är redo för din egen berättelse väljer du Lägg till en bok. Klistra in texten eller öppna en textfil. Resten får ta den tid det tar.`;
$('demo').onclick=async()=>{try{const result=await api('/api/book',{title:'Det lilla biblioteket vid havet',text:demoText,voice,position:0});await refreshLibrary();await openBook(result.id);}catch(error){report(error);}};
$('quit').onclick=async()=>{stop('Avslutar…');await savePosition();try{clearTimeout(settingsTimer);await api('/api/settings',settingsSnapshot());if(window.chrome?.webview){window.chrome.webview.postMessage('bab:quit');return;}if(window.pywebview?.api){await window.pywebview.api.quit(token);return;}await api('/api/quit',{});ready=false;setStatus('BAB är avslutat. Du kan stänga fönstret.');$('play').disabled=true;document.querySelectorAll('button').forEach(b=>b.disabled=true);}catch(error){report(error);}};
window.addEventListener('pagehide',()=>{const snapshot=positionSnapshot();if(snapshot)fetch('/api/position',{method:'POST',headers:{'Content-Type':'application/json','X-BAB-Token':token},body:JSON.stringify(snapshot),keepalive:true}).catch(()=>{});});
window.addEventListener('pagehide',()=>{if(ready)fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json','X-BAB-Token':token},body:JSON.stringify(settingsSnapshot()),keepalive:true}).catch(()=>{});});
document.addEventListener('visibilitychange',()=>{if(document.hidden)savePosition();});
setInterval(()=>{if(ready){api('/api/ping').catch(()=>{});if(book)savePosition();}},2500);
async function initialize(){
  try{const data=await api('/api/bootstrap');backgroundVoices=data.capabilities?.backgroundVoices!==false;catalog=data.voices;library=data.books;$('desktopShortcut').hidden=data.capabilities?.desktopShortcut===false;applySettings(data.settings);renderLibrary();renderVoices();renderBook();ready=true;if(data.settings.lastBook&&library.some(b=>b.id===data.settings.lastBook))await openBook(data.settings.lastBook);else if(library.length)await openBook(library[0].id);animate();}
  catch(error){setStatus('BAB kunde inte öppnas. Starta programmet från startfilen.');report(error);}
}
initialize();
