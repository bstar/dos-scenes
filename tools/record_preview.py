#!/usr/bin/env python3
"""Capture 15 seconds from the actual DOS renderer and losslessly optimize a native GIF."""
from pathlib import Path
import base64,bisect,json,os,shutil,struct,subprocess,sys
from PIL import Image,ImageChops,ImageSequence
R=Path(__file__).resolve().parents[1]
sdk=Path(os.environ.get('WATCOM',R/'build/toolchains/watcom'))
if sdk.is_dir():os.environ.update(WATCOM=str(sdk),INCLUDE=str(sdk/'h'),PATH=str(sdk/'binl64')+os.pathsep+os.environ['PATH'])
D=R/'build/preview';shutil.rmtree(D,ignore_errors=True);D.mkdir()
shutil.copytree(R/'build/scenes/island',D/'ISLAND',ignore=shutil.ignore_patterns('VOLUME.CFG','VOLUME.BAK','VOLSET.TMP','*.LOG','LAST.EGA'))
subprocess.run(['wcl','-q','-bt=dos','-0','-ml','-k8192','-fe=RECORD.EXE',str(R/'tools/preview_driver.c'),str(R/'build/runtime.o')],cwd=D,check=True)
config=D/'capture.conf';config.write_text(f'[sdl]\noutput=surface\n[dosbox]\nmachine=ega\n[cpu]\ncore=normal\ncputype=386\ncycles=fixed 100000\n[sblaster]\nsbtype=none\noplmode=opl2\n[autoexec]\nmount c {D}\nc:\nRECORD > CAPTURE.TXT\nexit\n')
box=os.environ.get('DOSBOX') or shutil.which('dosbox-x');assert box
subprocess.run([box,'-conf',str(config),'-noconsole'],env=dict(os.environ,SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy'),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=45,check=True)
raw=(D/'TAKE.RAW').read_bytes();assert len(raw)%32008==0
records=[]
for off in range(0,len(raw),32008):
 tick,frame=struct.unpack_from('<II',raw,off);indexed=Image.new('L',(320,200))
 for p in range(4):
  plane=Image.frombytes('1',(320,200),raw[off+8+p*8000:off+8+(p+1)*8000]).convert('L').point([0]*255+[1<<p]);indexed=ImageChops.add(indexed,plane)
 records.append((tick,frame,indexed))
assert len(records)>=180 and records[-1][0]-records[0][0]>=8400
codes=(D/'ISLAND/PALETTE.BIN').read_bytes();palette=bytes(c for v in codes for c in (170*((v>>2)&1)+85*((v>>5)&1),170*((v>>1)&1)+85*((v>>4)&1),170*(v&1)+85*((v>>3)&1)))
sys.path.insert(0,str(R/'tests'));from reference import compose
for tick,frame,indexed in records[::14]+records[-1:]:assert list(indexed.tobytes())==compose(D/'ISLAND',tick,frame-1)
ticks=[r[0] for r in records];frames=[];delays=[];starts=[];fps=14;seconds=15
for i in range(fps*seconds):
 target=ticks[0]+i*(1193182/2131)/fps;at=bisect.bisect_left(ticks,target);choices=[n for n in (at-1,at) if 0<=n<len(records)];at=min(choices,key=lambda n:abs(ticks[n]-target))
 image=Image.frombytes('P',(320,200),records[at][2].tobytes());image.putpalette(palette);frames.append(image);starts.append(round(i*100/fps));delays.append((round((i+1)*100/fps)-starts[-1])*10)
assert sum(delays)==15000
unoptimized=D/'full.gif';frames[0].save(unoptimized,save_all=True,append_images=frames[1:],duration=delays,loop=0,optimize=False,disposal=1)
candidates=[]
for level in (2,3):
 dest=D/f'optimized-{level}.gif';subprocess.run(['gifsicle',f'-O{level}','--no-comments','--no-names',str(unoptimized),'-o',str(dest)],check=True);candidates.append(dest)
output=D/'ISLAND.GIF';shutil.copyfile(min(candidates,key=lambda p:p.stat().st_size),output)
with Image.open(output) as gif:
 assert gif.size==(320,200) and gif.info['loop']==0
 elapsed=0
 for frame in ImageSequence.Iterator(gif):
  duration=frame.info['duration']//10;actual=frame.convert('RGB').tobytes();at=bisect.bisect_right(starts,elapsed)-1
  assert actual==frames[at].convert('RGB').tobytes()
  for i in range(at+1,len(starts)):
   if starts[i]>=elapsed+duration:break
   assert actual==frames[i].convert('RGB').tobytes()
  elapsed+=duration
 assert elapsed==1500
svg=R/'docs/island.svg';svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="640" height="400" viewBox="0 0 640 400">\n<title>DOS island scene - 15 seconds</title>\n<image width="640" height="400" style="image-rendering:pixelated" href="data:image/gif;base64,'+base64.b64encode(output.read_bytes()).decode()+'"/>\n</svg>\n')
report=dict(duration_ms=15000,native_size=[320,200],display_size=[640,400],fps=fps,captured_frames=len(records),gif_bytes=output.stat().st_size,unoptimized_bytes=unoptimized.stat().st_size,lossless_verified=True)
(D/'validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report));print(output);print(svg)
