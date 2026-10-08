"""Entirely local Swedish synthesis; models and runtime ship with BAB."""
from pathlib import Path
import sys,json,threading,re,io,wave,hashlib,time
from difflib import SequenceMatcher
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'offline_packages'))
import numpy as np
import onnxruntime as ort
from piper import PiperVoice,SynthesisConfig
from piper.config import PiperConfig

_voices={};_load_lock=threading.Lock();_inference=threading.Lock()
_base_locks={};_locks_lock=threading.Lock()

def load_voice(gender):
    with _load_lock:
        if gender not in _voices:
            if sys.platform=='darwin':
                # Keep one model resident on Mac; changing style reuses that model.
                _voices.clear()
            name='nst' if gender=='male' else 'alma'
            model=ROOT/'models'/f'sv_SE-{name}-medium.onnx'
            settings=ort.SessionOptions();settings.intra_op_num_threads=1 if sys.platform=='darwin' else 2;settings.inter_op_num_threads=1
            settings.execution_mode=ort.ExecutionMode.ORT_SEQUENTIAL
            settings.add_session_config_entry('session.intra_op.allow_spinning','0')
            settings.add_session_config_entry('session.inter_op.allow_spinning','0')
            settings.enable_mem_pattern=True
            session=ort.InferenceSession(str(model),sess_options=settings,providers=['CPUExecutionProvider'])
            config=PiperConfig.from_dict(json.loads(Path(str(model)+'.json').read_text(encoding='utf-8')))
            _voices[gender]=PiperVoice(session=session,config=config)
        return _voices[gender]

def warmup():
    for gender in ['female','male']:load_voice(gender)

def contextual_phonemes(voice,text):
    """Use phrase-level pronunciation; isolated words are alignment references only.

    Context changes stress and pronunciation in Swedish. Never feed the isolated
    word reference to the model. Map those references monotonically to the actual
    phrase phonemes so numbers/abbreviations can still belong to one source word.
    """
    reference=[];reference_owners=[]
    source_words=re.findall(r'\S+',text)
    for index,word in enumerate(source_words):
        groups=voice.phonemize(word.replace('[[','').replace(']]',''))
        phones=[p for group in groups for p in group]
        if reference:reference.append(' ');reference_owners.append(index)
        reference.extend(phones);reference_owners.extend([index]*len(phones))
    groups=voice.phonemize(text.replace('[[','').replace(']]',''))
    phonemes=[]
    for group in groups:
        if phonemes:phonemes.append(' ')
        phonemes.extend(group)
    if not reference or not phonemes:raise ValueError('Textavsnittet innehåller inga läsbara ord.')
    owners=[]
    for tag,a,b,c,d in SequenceMatcher(None,reference,phonemes,autojunk=False).get_opcodes():
        if tag=='equal':owners.extend(reference_owners[a:b])
        elif tag in ('insert','replace'):
            for j in range(d-c):
                at=min(len(reference_owners)-1,a+(j*(b-a)//max(1,d-c)))
                owners.append(reference_owners[at])
    assert len(owners)==len(phonemes)
    return phonemes,owners

def synthesize_base(text,gender):
    voice=load_voice(gender)
    phonemes,owners=contextual_phonemes(voice,text)
    mapping=voice.config.phoneme_id_map
    ids=list(mapping['^'])+list(mapping['_']);id_owners=[-1]*len(ids)
    for phone,owner in zip(phonemes,owners):
        if phone not in mapping:continue
        part=list(mapping[phone])+list(mapping['_']);ids.extend(part);id_owners.extend([owner]*len(part))
    ids.extend(mapping['$']);id_owners.extend([-1]*len(mapping['$']))
    with _inference:
        samples,durations=voice.phoneme_ids_to_audio(ids,SynthesisConfig(noise_scale=.5,noise_w_scale=.65),include_alignments=True)
    if durations is None or len(durations)!=len(ids):raise ValueError('Den lokala röstmodellens ordmarkering saknas.')
    peak=float(np.max(np.abs(samples)))
    samples=(samples/max(peak,1e-6)*.92).astype(np.float32)
    cursor=0;positions={};rate=voice.config.sample_rate
    for owner,count in zip(id_owners,durations):
        count=int(count)
        if owner>=0:
            if owner not in positions:positions[owner]=[cursor,cursor+count]
            else:positions[owner][1]=cursor+count
        cursor+=count
    timings=[dict(word=i,lastWord=i,start=start/rate,duration=(end-start)/rate) for i,(start,end) in positions.items()]
    if not timings:raise ValueError('Textavsnittet innehåller inga läsbara ord.')
    return samples,rate,timings

def get_base(text,gender,cache):
    key=hashlib.sha256(('bab-local-base-2\0'+gender+'\0'+text).encode()).hexdigest()
    path=Path(cache)/f'base-{key}.npz'
    with _locks_lock:lock=_base_locks.setdefault(key,threading.Lock())
    with lock:
        if path.is_file():
            try:
                with np.load(path,allow_pickle=False) as data:return data['samples'],int(data['rate']),json.loads(str(data['timings']))
            except (OSError,ValueError):pass
        samples,rate,timings=synthesize_base(text,gender)
        temp=path.with_suffix('.tmp')
        with temp.open('wb') as file:np.savez(file,samples=samples,rate=rate,timings=json.dumps(timings))
        temp.replace(path)
        return samples,rate,timings

def synthesize(text,profile,cache):
    samples,rate,timings=get_base(text,profile['gender'],cache)
    # All styles share the same base render: changing style never reloads a model.
    pitch=float(profile['pitch'].replace('Hz',''))
    tempo=float(profile['rate'].replace('%',''))
    # Small variations keep the recorded character; the separate playback speed
    # control handles larger tempo changes with pitch preservation in the player.
    factor=2**(pitch/360)*(1+tempo/400)
    if abs(factor-1)>.0001:
        samples=np.interp(np.arange(0,len(samples),factor),np.arange(len(samples)),samples).astype(np.float32)
        timings=[dict(t,start=t['start']/factor,duration=t['duration']/factor) for t in timings]
    pcm=(np.clip(samples,-1,1)*32767).astype('<i2').tobytes()
    output=io.BytesIO()
    with wave.open(output,'wb') as wav:
        wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(rate);wav.writeframes(pcm)
    return output.getvalue(),timings
