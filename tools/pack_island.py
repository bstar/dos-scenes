#!/usr/bin/env python3
"""Build the bundled island scene, or regenerate it from local source assets."""
import argparse,json,shutil
from pathlib import Path
from scene_format import details,twinkles
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--assets',type=Path,help='Optional locally extracted source assets');p.add_argument('--output',type=Path,default=ROOT/'build/scenes/island');a=p.parse_args()
 source=a.assets or ROOT/'scenes/island/pack'
 background='ORIGINAL.EGA' if a.assets else 'SCENE.EGA'
 required=[background,'MOON.BIN','PALETTE.BIN','SKY.MSK','CLOUD.BIN','CLOUD.MOT','FIRE.BIN','STAR1.BIN','STAR2.BIN','SONG2.OPL','SONG3.OPL','SONG4.OPL']
 for name in required:
  if not (source/name).is_file():p.error('Missing local asset: '+name)
 a.output.mkdir(parents=True,exist_ok=True)
 for name in required:shutil.copyfile(source/name,a.output/('SCENE.EGA' if name==background else name))
 (a.output/'TWINKLE.BIN').write_bytes(twinkles(json.loads((ROOT/'scenes/island/twinkle.json').read_text())))
 data=json.loads((ROOT/'scenes/island/details.json').read_text());(a.output/'DETAILS.BIN').write_bytes(details(**data))
 (a.output/'SCENE.CFG').write_bytes(b'NAME Melee Island\r\nFIRE_X 136\r\nFIRE_Y 0\r\nMOON_SECONDS 3600\r\nMOON_DX 88\r\nMOON_DY 80\r\n')
 (a.output/'PLAYLIST.CFG').write_bytes(b'SONG2.OPL\r\nSONG3.OPL\r\nSONG4.OPL\r\n# INTRO.OPL is intentionally disabled.\r\n')
 (a.output/'CREDITS.TXT').write_bytes((ROOT/'scenes/island/CREDITS.md').read_text().replace('\r\n','\n').replace('\n','\r\n').encode('ascii'))
 print(a.output)
if __name__=='__main__':main()
