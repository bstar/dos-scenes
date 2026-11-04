#!/usr/bin/env python3
"""Actual DOS EGA/OPL2 output at wall-clock and accelerated scene times."""
from pathlib import Path
import os,subprocess,shutil,re,argparse,json,struct,csv
from reference import decode,compose
R=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser();p.add_argument('--pack',type=Path,default=R/'build/scenes/demo');a=p.parse_args()
box=os.environ.get('DOSBOX') or shutil.which('dosbox-x')
if not box:raise SystemExit('Set DOSBOX to DOSBox-X or put dosbox-x on PATH')
results=[];twinkle_seen=False;twinkle_present=False
for seconds,variant,cycles in [(s,"normal",3000) for s in [0,1,2,4,60,100,180,899,900,1799,1800,2700,3599,3600,7200]]+[(0,"fast",200000),(0,"slow",12000),(0,"no-opl",6000),(1800,"reverse",6000)]:
 d=R/'build'/('test-player-'+str(seconds)+'-'+variant);shutil.rmtree(d,ignore_errors=True);d.mkdir();shutil.copytree(a.pack,d/'SCENE',dirs_exist_ok=True,ignore=shutil.ignore_patterns("VOLUME.CFG","VOLUME.BAK","VOLSET.TMP"));shutil.copyfile(R/'build/SCENE.EXE',d/'SCENE.EXE')
 if variant=='reverse':
  config=d/'SCENE/SCENE.CFG';config.write_text(config.read_text()+'\nMOON_DX -90\nMOON_DY -10\n')
 cfg=d/'test.conf';cfg.write_text(f'[sdl]\noutput=surface\n[dosbox]\nmachine=ega\n[cpu]\ncore=normal\ncputype=386\ncycles=fixed {cycles}\n[sblaster]\nsbtype=none\noplmode={"none" if variant=="no-opl" else "opl2"}\n[autoexec]\nmount c {d}\nc:\nSCENE C:\\SCENE /LOG {"/SLOWOPL" if variant=="slow" else ""} /AT={seconds} /FRAMES=4 /DUMP > RESULT.TXT\nexit\n')
 subprocess.run([box,'-conf',str(cfg),'-noconsole'],cwd=R,env=dict(os.environ,SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy'),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=20,check=True)
 text=(d/'RESULT.TXT').read_text();t=int(re.search(r'Scene ticks: (\d+)',text)[1]);assert ('AdLib: absent' if variant=='no-opl' else 'AdLib: present') in text,text
 actual=decode((d/'SCENE/LAST.EGA').read_bytes());expected=compose(d/'SCENE',t,3)
 if (d/'SCENE/TWINKLE.BIN').exists():
  twinkle_present=True;b=(d/'SCENE/TWINKLE.BIN').read_bytes()
  for i in range(struct.unpack_from('<H',b,4)[0]):
   x,y,period,phase,duration,source,off=struct.unpack_from('<5H2B',b,6+i*12)
   if (t+phase)%period<duration and actual[y*320+x]==off:twinkle_seen=True
 mismatch=sum(x!=y for x,y in zip(actual,expected));assert mismatch==0,(seconds,mismatch,text)
 log=(d/'SCENE/SCENE.LOG').read_text();assert ',pit_guard=1,' in log
 lines=log.splitlines();header=next(i for i,s in enumerate(lines) if s.startswith('reason,'));rows=list(csv.DictReader(lines[header:]))
 assert all(r['fault']=='0' and r['pit_guard']=='1' and r['pit_timeouts']=='0' for r in rows)
 assert min(int(r['addr_floor']) for r in rows)>=(28 if variant=='slow' else 14)
 assert min(int(r['data_floor']) for r in rows)>=(136 if variant=='slow' else 68)
 if seconds>=3600:assert not any(c in (2,4,10) for c in actual) if 'island' in str(a.pack) else True
 results.append(dict(seconds=seconds,variant=variant,emulator_cycles=cycles,exact_pixels=64000,scene_ticks=t));print('PASS scene',seconds,variant,':64000 exact pixels')
if twinkle_present:assert twinkle_seen,'No blink was exercised in the captured DOS frames'
(R/'build/player-validation.json').write_text(json.dumps(results,indent=2)+'\n')
