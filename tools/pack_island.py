#!/usr/bin/env python3
"""Build a private island scene pack from locally extracted assets; no downloads."""
import argparse,json,shutil
from pathlib import Path
from scene_format import details
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--assets',type=Path,required=True);p.add_argument('--output',type=Path,default=ROOT/'build/scenes/island');a=p.parse_args()
 required=['ORIGINAL.EGA','MOON.BIN','PALETTE.BIN','SKY.MSK','CLOUD.BIN','CLOUD.MOT','FIRE.BIN','STAR1.BIN','STAR2.BIN','SONG2.OPL','SONG3.OPL','SONG4.OPL']
 for name in required:
  if not (a.assets/name).is_file():p.error('Missing local asset: '+name)
 a.output.mkdir(parents=True,exist_ok=True)
 for name in required:shutil.copyfile(a.assets/name,a.output/('SCENE.EGA' if name=='ORIGINAL.EGA' else name))
 data=json.loads((ROOT/'scenes/island/details.json').read_text());(a.output/'DETAILS.BIN').write_bytes(details(**data))
 (a.output/'SCENE.CFG').write_bytes(b'NAME Melee Island\r\nFIRE_X 136\r\nFIRE_Y 0\r\nMOON_SECONDS 3600\r\nMOON_DX 88\r\nMOON_DY 80\r\n')
 (a.output/'PLAYLIST.CFG').write_bytes(b'SONG2.OPL\r\nSONG3.OPL\r\nSONG4.OPL\r\n# INTRO.OPL is intentionally disabled.\r\n')
 shutil.copyfile(ROOT/'scenes/island/CREDITS.md',a.output/'CREDITS.TXT')
 print(a.output)
if __name__=='__main__':main()
