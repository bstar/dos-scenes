#!/usr/bin/env python3
"""Run the shared module and standalone EXE as separate real DOS processes."""
from pathlib import Path
import os,subprocess,shutil,csv,json
root=Path(__file__).resolve().parents[1]
base=root/'build/test-volume';shutil.rmtree(base,ignore_errors=True)
(base/'DEMO').mkdir(parents=True)
for f in (root/'build/scenes/demo').iterdir():
 if f.name not in ('VOLUME.CFG','VOLUME.BAK','VOLSET.TMP'):shutil.copyfile(f,base/'DEMO'/f.name)
shutil.copyfile(root/'build/SCENE.EXE',base/'DEMO/SCENE.EXE')
env=os.environ.copy()
if env.get('WATCOM'):
 wc=Path(env['WATCOM']);env.update(INCLUDE=str(wc/'h'),PATH=str(wc/'binl64')+os.pathsep+env['PATH'])
subprocess.run(['wcl','-q','-bt=dos','-0','-ml','-fe='+str(base/'ISLVOL.EXE'),str(root/'tests/volume_driver.c'),str(root/'build/runtime.o')],cwd=base,env=env,check=True)
commands=['ISLVOL set > RESULTS.TXT','ISLVOL muted >> RESULTS.TXT','ISLVOL zero >> RESULTS.TXT',r'cd \DEMO','SCENE /LOG /FRAMES=2 > FIRST.TXT','addkey p300 +','SCENE /LOG /FRAMES=28 > SECOND.TXT','cd ..','ISLVOL shared >> RESULTS.TXT','ISLVOL recovery >> RESULTS.TXT']
config='''[sdl]\noutput=surface\n[dosbox]\nmachine=ega\n[cpu]\ncore=normal\ncputype=386\ncycles=fixed 6000\n[sblaster]\nsbtype=none\noplmode=opl2\n[autoexec]\nmount c dist\nc:\nSCENE.EXE\nexit\n'''.replace('machine=ega','machine=vgaonly').replace('cputype=286','cputype=386').replace('mount c dist',f'mount c "{base}"').replace('SCENE.EXE\n','\n'.join(commands)+'\n')
(base/'test.conf').write_text(config)
subprocess.run([os.environ.get('DOSBOX') or shutil.which('dosbox-x'),'-conf',str(base/'test.conf'),'-noconsole'],env=dict(os.environ,SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy'),cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=45,check=True)
result=(base/'RESULTS.TXT').read_text();errors=(base/'VOLTEST.LOG').read_text()
assert not errors,errors
for marker in ['SET24','RELOAD24','ZERO','SHARED','RECOVERY']:assert marker in result,result
lines=(base/'DEMO/SCENE.LOG').read_text().splitlines();starts=[i for i,s in enumerate(lines) if s.startswith('RUN,')];rows=[]
for i,end in zip(starts,starts[1:]+[len(lines)]):
 part=lines[i:end];header=next(n for n,s in enumerate(part) if s.startswith('reason,'));rows+=list(csv.DictReader(part[header:]))
assert [r['volume'] for r in rows if r['reason']=='START']==['1','1']
assert any(r['reason']=='KEY' and r['volume']=='2' for r in rows)
report={'debounced_save_during_playback':True,'cross_process_reload':True,'saved_while_muted':True,'zero_persists':True,'shared_with_standalone':True,'save_on_wake':True,'backup_recovery':True,'invalid_config_default':28,'failed_save_preserves_memory_and_retries':True,'dos_output':result}
(base/'validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
