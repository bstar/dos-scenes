#!/usr/bin/env python3
"""Package built DOS executables and the original demo; no installer or private assets."""
import argparse,hashlib,re,subprocess,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--output',type=Path,default=ROOT/'dist');args=p.parse_args()
version=(ROOT/'VERSION').read_text().strip()
if not re.fullmatch(r'\d+\.\d+\.\d+',version):p.error('VERSION must contain major.minor.patch')
commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
files={name:(ROOT/'build'/name).read_bytes() for name in ('SCENE.EXE','SCENETSR.EXE')}
for name,data in files.items():
 if data[:2]!=b'MZ':p.error(name+' is not a DOS MZ executable')
# Explicit allowlist prevents user settings, logs or local island assets entering a release.
for name in ('SCENE.EGA','SKY.MSK','PALETTE.BIN','MOON.BIN','CLOUD.BIN','DETAILS.BIN','SCENE.CFG','DEMO.OPL','PLAYLIST.CFG'):
 files['DEMO/'+name]=(ROOT/'build/scenes/demo'/name).read_bytes()
def text(s):return s.replace('\r\n','\n').replace('\n','\r\n').encode('ascii')
files['LICENSE.TXT']=text((ROOT/'LICENSE').read_text())
files['VERSION.TXT']=text(f'DOS Scenes {version}\nSource commit: {commit}\nTarget: real-mode MS-DOS, Open Watcom 2, 8086 integer code\nSource: https://github.com/bstar/dos-scenes\n')
files['README.TXT']=text(f'''DOS SCENES {version}

Copy this directory to C:\\SCENES. No setup program is needed.

Standalone player (EGA or VGA; AdLib optional):
  C:
  CD \\SCENES
  SCENE C:\\SCENES\\DEMO

Optional resident screensaver (DOS 5+, VGA 80x25 text, page 0):
  SCENETSR C:\\SCENES\\DEMO /IDLE=120
  Ctrl-Alt-S requests the scene at the next safe DOS idle point.
  /IDLE=0 selects hotkey-only activation.
  SCENETSR /OFF disables activation; /ON enables it; /STATUS reports state.
  Reboot removes the TSR. It uses about 102KB plus active scene memory.
  It waits if a foreground program does not yield to DOS and defers in graphics.

Controls: +/- volume (saved), M mute/restart, N next song.
Esc exits the standalone player; other keys wake the resident screensaver.
Use /SLOWOPL for additional AdLib write recovery delay on faster computers.
The runtime already uses classic AdLib delays and a bounded PIT guard.

DEMO contains the original MIT-licensed Night Coast scene and OPL2 motif.
The island screenshot shown on GitHub is an external scene preview. Game art,
stream crops and third-party music are not included in this archive. To build
that scene from your own assets, see the island guide and original credits:
https://github.com/bstar/dos-scenes/tree/main/scenes/island

Source, build instructions, scene format, limitations and credits:
https://github.com/bstar/dos-scenes

The player and NETFTP integration were checked on a physical 386SX-16/AdLib.
Resident mode has been tested in DOSBox-X; physical TSR acceptance is pending.
See LICENSE.TXT for the MIT terms covering the included code and demo.
''')
args.output.mkdir(parents=True,exist_ok=True);archive=args.output/'DOSSCENE.ZIP'
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for name,data in sorted(files.items()):
  if any(not re.fullmatch(r'[A-Z0-9_]{1,8}(\.[A-Z0-9_]{1,3})?',part) for part in name.split('/')):p.error('Not DOS 8.3: '+name)
  info=zipfile.ZipInfo(name,(2026,1,1,0,0,0));info.create_system=0;info.external_attr=0x20;info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,data)
digest=hashlib.sha256(archive.read_bytes()).hexdigest();(args.output/'SHA256.TXT').write_bytes(text(f'{digest}  {archive.name}\n'))
print(archive);print(digest)
