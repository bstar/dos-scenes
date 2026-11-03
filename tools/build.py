#!/usr/bin/env python3
"""Build directly runnable DOS files with Open Watcom; no setup utility."""
import argparse,os,subprocess,shutil,struct
from pathlib import Path
R=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--watcom',type=Path,default=Path(os.environ['WATCOM']) if os.environ.get('WATCOM') else None);a=p.parse_args();env=os.environ.copy()
if a.watcom:
 env['WATCOM']=str(a.watcom.resolve());env['INCLUDE']=str(a.watcom.resolve()/'h');env['PATH']=str(a.watcom.resolve()/'binl64')+os.pathsep+env['PATH']
B=R/'build';B.mkdir(exist_ok=True)
def run(args):subprocess.run(args,cwd=B,env=env,check=True)
run(['wcl','-q','-bt=dos','-0','-ml','-os','-k8192','-fe=SCENE.EXE',str(R/'src/runtime.c')])
run(['wcc','-q','-0','-ml','-os','-dDOS_SCENES_EMBEDDED','-s','-fo=runtime.o',str(R/'src/runtime.c')])
if (R/'src/tsr.c').exists():
 run(['wcc','-q','-0','-ml','-os','-zu','-s','-fo=tsr.o',str(R/'src/tsr.c')])
 run(['wasm','-q','-0','-ml','-fo=tsrstack.o',str(R/'src/tsrstack.asm')])
 run(['wlink','system','dos','option','stack=8192','option','map','name','SCENETSR.EXE','file','tsr.o,runtime.o,tsrstack.o'])
 # DOS MZ max-allocation is the minimum required image tail, not all free RAM.
 image=bytearray((B/'SCENETSR.EXE').read_bytes())
 struct.pack_into('<H',image,12,struct.unpack_from('<H',image,10)[0])
 (B/'SCENETSR.EXE').write_bytes(image)
run(['python3',str(R/'tools/make_demo.py')])

run(['python3',str(R/'tools/pack_island.py')])
