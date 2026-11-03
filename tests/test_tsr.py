#!/usr/bin/env python3
"""Boot the real resident EXE, then call it from a different DOS process."""
from pathlib import Path
import os,subprocess,struct,shutil,sys
R=Path(__file__).resolve().parents[1];B=R/'build';D=B/'test-tsr';D.mkdir(exist_ok=True)
for n in ['SCENETSR.EXE']:shutil.copyfile(B/n,D/n)
shutil.copytree(B/'scenes/demo',D/'DEMO',dirs_exist_ok=True,ignore=shutil.ignore_patterns('VOLUME.CFG','VOLUME.BAK','VOLSET.TMP'))
env=os.environ.copy();wc=Path(env['WATCOM']) if env.get('WATCOM') else None
if wc is not None:env.update(WATCOM=str(wc),INCLUDE=str(wc/'h'),PATH=str(wc/'binl64')+os.pathsep+env['PATH'])
subprocess.run(['wcl','-q','-bt=dos','-0','-ml','-k4096','-fe=DRIVER.EXE',str(R/'tests/tsr_driver.c')],cwd=D,env=env,check=True)
p=D/'DRIVER.EXE';b=bytearray(p.read_bytes());struct.pack_into('<H',b,12,struct.unpack_from('<H',b,10)[0]);p.write_bytes(b)
for n in ['TSRPASS.TXT','TSRERR.TXT']:(D/n).unlink(missing_ok=True)
conf=D/'test.conf';conf.write_text(f'[sdl]\noutput=surface\n[cpu]\ncore=normal\ncputype=386\nfpu=false\ncycles=fixed 6000\n[sblaster]\nsbtype=none\noplmode=opl2\n[autoexec]\nmount c {D}\nc:\nSCENETSR C:\\DEMO /IDLE=0 > LOAD.TXT\nSCENETSR /STATUS > STATUS.TXT\n{('addkey p700 c-a-s p400 - p300 + p800 escape' if '--hotkey' in sys.argv else 'addkey p600 - p300 + p900 escape')}\nDRIVER{(' hotkey' if '--hotkey' in sys.argv else '')}\nSCENETSR /STATUS > AFTER.TXT\nexit\n')
box=os.environ.get('DOSBOX') or shutil.which('dosbox-x')
subprocess.run([box,'-conf',str(conf),'-noconsole'],env=dict(env,SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy'),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=40,check=True)
assert (D/'TSRPASS.TXT').exists(),(D/'TSRERR.TXT').read_text() if (D/'TSRERR.TXT').exists() else (D/'LOAD.TXT').read_text()
print((D/'LOAD.TXT').read_text().strip());print((D/'TSRPASS.TXT').read_text().strip());print((D/'AFTER.TXT').read_text().strip())
