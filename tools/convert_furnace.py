#!/usr/bin/env python3
"""Export Furnace's real OPL2 performance to the preloaded DOS register stream.

Preserves instruments, volume changes, percussion and both ocean layers.
Requires Furnace only on the host. Rejects other chips and dual OPL2 banks.
"""
import argparse,gzip,hashlib,json,os,struct,subprocess,shutil
from pathlib import Path
from opl_stream import RATE,write_opl

def read_vgm(path):
 b=Path(path).read_bytes()
 if b[:2]==b'\x1f\x8b':b=gzip.decompress(b)
 if len(b)<0x54 or b[:4]!=b'Vgm ':raise ValueError('Invalid VGM header')
 clock=struct.unpack_from('<I',b,0x50)[0]
 if clock&0xc0000000 or not 3500000<=clock<=3600000:raise ValueError('Requires a single standard-clock YM3812')
 offset=struct.unpack_from('<I',b,0x34)[0];pos=0x34+offset if offset else 0x40
 looping=bool(struct.unpack_from('<I',b,0x1c)[0])
 samples=0;events=[]
 while pos<len(b):
  cmd=b[pos];pos+=1
  if cmd==0x5a:
   reg,val=b[pos:pos+2];pos+=2
   events.append((round(samples*RATE/44100),reg,val))
  elif cmd==0x61:samples+=struct.unpack_from('<H',b,pos)[0];pos+=2
  elif cmd==0x62:samples+=735
  elif cmd==0x63:samples+=882
  elif 0x70<=cmd<=0x7f:samples+=(cmd&15)+1
  elif cmd==0x66:
   # Furnace writes next-loop setup in its last timestamp group, then appends
   # a final tick wait. Remove that setup so the next song starts cleanly.
   if looping and events:
    last=events[-1][0]
    events=[event for event in events if event[0]!=last]
   return events,samples/44100
  else:raise ValueError(f'Non-OPL2 or unsupported VGM command0x{cmd:02x}')
 raise ValueError('Missing VGM end command')

def convert(vgm,output):
 events,duration=read_vgm(vgm)
 if not events:raise ValueError('Empty OPL2 performance')
 # Furnace may emit next-loop setup at EOF. Release every key immediately,
 # including percussion; then retain the existing quarter-second release gap.
 end=max(events[-1][0],round(duration*RATE))
 events.extend((end,0xb0+c,0) for c in range(9));events.append((end,0xbd,0))
 for offset in [0,1,2,8,9,10,16,17,18]:
  events.extend([(end,0x40+offset,63),(end,0x43+offset,63)])
 size=write_opl(events,output)
 counts={}
 for t,_,_ in events:counts[t]=counts.get(t,0)+1
 return {'source_vgm':str(vgm),'bytes':size,'source_seconds':duration,
         'loop_seconds':(end+round(RATE/4))/RATE,'opl_timer_hz':RATE,
         'source_writes':len(events)-28,'max_writes_per_tick':max(counts.values()),
         'melodic_and_rhythm_keys_released':True}

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('project',type=Path)
 p.add_argument('--furnace',type=Path,default=Path(shutil.which('furnace') or 'furnace'))
 p.add_argument('--output',type=Path,default=Path('build/SONG.OPL'))
 p.add_argument('--vgm',type=Path,default=Path('build/song.vgm'))
 a=p.parse_args();a.vgm.parent.mkdir(parents=True,exist_ok=True);a.output.parent.mkdir(parents=True,exist_ok=True)
 subprocess.run([str(a.furnace),'-console','-nostatus','-nocontrols','-loglevel','warning','-vgmout',str(a.vgm),'-loops','0',str(a.project)],env=dict(os.environ,SDL_AUDIODRIVER='dummy'),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)
 result=convert(a.vgm,a.output);result['furnace_project']=str(a.project);result['project_sha256']=hashlib.sha256(a.project.read_bytes()).hexdigest()
 a.vgm.with_suffix('.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
