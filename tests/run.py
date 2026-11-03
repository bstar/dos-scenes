#!/usr/bin/env python3
"""Build and run actual DOS scene, volume and resident-mode checks."""
from pathlib import Path
import argparse,os,subprocess,sys,shutil
R=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--no-build',action='store_true');args=p.parse_args()
if not (os.environ.get('DOSBOX') or shutil.which('dosbox-x')):
 raise SystemExit('DOSBox-X is required; use nix develop or set DOSBOX')
def run(*argv):subprocess.run([sys.executable,*map(str,argv)],cwd=R,check=True)
if not args.no_build:run(R/'tools/build.py')
run(R/'tests/test_player.py')
run(R/'tests/test_player.py','--pack',R/'build/scenes/island')
run(R/'tests/test_volume.py')
run(R/'tests/test_tsr.py')
run(R/'tests/test_tsr.py','--hotkey')
print('PASS all DOS runtime checks')
