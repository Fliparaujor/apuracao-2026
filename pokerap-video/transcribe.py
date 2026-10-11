import sys,json
from faster_whisper import WhisperModel
m=WhisperModel(sys.argv[2],device="cpu",compute_type="int8")
import subprocess,numpy as np
pcm=subprocess.run(["ffmpeg","-v","error","-i",sys.argv[1],"-ac","1","-ar","16000","-f","s16le","-"],capture_output=True).stdout
audio=np.frombuffer(pcm,np.int16).astype(np.float32)/32768
segs,info=m.transcribe(audio,word_timestamps=True,language="en",vad_filter=False,
  initial_prompt="Pokérap. Electrode, Diglett, Nidoran, Mankey, Venusaur, Rattata, Fearow, Pidgey. Gotta catch 'em all, Pokémon!")
out=[]
for s in segs:
    for w in s.words: out.append([round(w.start,2),round(w.end,2),w.word.strip()])
    print(f"[{s.start:6.2f}-{s.end:6.2f}] {s.text}",flush=True)
json.dump(out,open(sys.argv[3],"w"))
