#!/usr/bin/env python3
"""Exercise all three island songs from the actual DOS release ZIP."""
from pathlib import Path
import hashlib,os,re,shutil,subprocess,sys,zipfile
from reference import decode,compose
R=Path(__file__).resolve().parents[1];D=R/'build/test-release';shutil.rmtree(D,ignore_errors=True);D.mkdir()
archive=R/'dist/DOSSCENE.ZIP'
assert hashlib.sha256(archive.read_bytes()).hexdigest()==(R/'dist/SHA256.TXT').read_text().split()[0]
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 names=z.namelist();assert not any(Path(n).name in ('VOLUME.CFG','VOLUME.BAK','VOLSET.TMP','INTRO.OPL') for n in names)
 z.extractall(D)
for n in ('SCENE.EXE','SCENETSR.EXE'):assert (D/n).read_bytes()==(R/'build'/n).read_bytes()
playlist=[s for s in (D/'ISLAND/PLAYLIST.CFG').read_text().splitlines() if s and not s.startswith('#')]
assert playlist==['SONG2.OPL','SONG3.OPL','SONG4.OPL']
credits=(D/'ISLAND/CREDITS.TXT').read_text();assert all(n in credits for n in ('Barry Taylor','Lesley Nelson','Video Game History Foundation'))
commands=[]
for track in range(1,4):commands.extend([f'SCENE C:\\ISLAND /LOG /TRACK={track} /FRAMES=28 /DUMP > TRACK{track}.TXT',f'COPY ISLAND\\LAST.EGA VIEW{track}.EGA > NUL'])
commands.extend(['SCENETSR C:\\ISLAND /IDLE=0 > TSR.TXT','SCENETSR /STATUS > STATUS.TXT','SCENETSR /OFF','exit'])
config=D/'run.conf';config.write_text(f'[sdl]\noutput=surface\n[cpu]\ncore=normal\ncputype=386\nfpu=false\ncycles=fixed 6000\n[sblaster]\nsbtype=none\noplmode=opl2\n[autoexec]\nmount c {D}\nc:\n'+'\n'.join(commands)+'\n')
box=os.environ.get('DOSBOX') or shutil.which('dosbox-x')
subprocess.run([box,'-conf',str(config),'-noconsole'],env=dict(os.environ,SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy'),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=40,check=True)
for track in range(1,4):
 output=(D/f'TRACK{track}.TXT').read_text();assert 'AdLib: present' in output and f'current: {track};' in output and f'Played track mask: {1<<(track-1)}' in output,output
 t=int(re.search(r'Scene ticks: (\d+)',output)[1]);assert decode((D/f'VIEW{track}.EGA').read_bytes())==compose(D/'ISLAND',t,27)
 print(f'PASS release island track {track}: AdLib playback, 64000 pixels')
assert 'resident' in (D/'TSR.TXT').read_text() and 'on' in (D/'STATUS.TXT').read_text()
print('PASS release ZIP: three songs, credits, disabled opening tune, clean settings and resident loading')
