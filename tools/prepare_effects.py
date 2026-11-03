#!/usr/bin/env python3
"""Composite the recovered moon and verified native mountain contour.
Clouds/meteors are recovered by track_video_effects.py; never redraw them here.
"""
from pathlib import Path
import json,hashlib
from extract_assets import planar,png
ROOT=Path(__file__).resolve().parents[1];dst=ROOT/'assets'
def main():
 data=(dst/'ORIGINAL.EGA').read_bytes()
 raw=bytearray(sum(((data[p*8000+y*40+x//8]>>(7-x%8))&1)<<p for p in range(4)) for y in range(200) for x in range(320))
 contour=json.loads((dst/'mountain-contour.json').read_text())['y_by_x']
 assert len(contour)==320 and all(0<=y<=200 for y in contour)
 mask=bytearray(8000)
 for x,boundary in enumerate(contour):
  for y in range(boundary):mask[y*40+x//8]|=128>>(x%8)
 (dst/'SKY.MSK').write_bytes(mask)
 native_used=set(raw)
 moon=(dst/'MOON.BIN').read_bytes()
 import struct,shutil
 x0,y0,w,h=struct.unpack_from('<HHHH',moon)
 assert len(moon)==8+w*h and x0+w<=320 and y0+h<=200
 for y in range(h):
  for x in range(w):
   color=moon[8+y*w+x]
   if color!=255:raw[(y0+y)*320+x0+x]=color
 info=json.loads((dst/'moon.json').read_text())
 import extract_assets as asset_format
 asset_format.PALETTE=info['palette_rgb']
 native_used|=set((dst/'FIRE.BIN').read_bytes()[6:])|set((dst/'CLOUD.BIN').read_bytes()[8:])-{255}
 for name in ['STAR1.BIN','STAR2.BIN']:
  d=(dst/name).read_bytes();count,_,_=struct.unpack_from('<HHH',d);off=6
  for _ in range(count):
   _,_,ww,hh,_=struct.unpack_from('<hhHHH',d,off);off+=10;native_used|=set(d[off:off+ww*hh])-{255};off+=ww*hh
 assert not native_used.intersection(map(int,info['modified_unused_slots'])), 'Moon palette would alter another asset'
 # Unused palette entries provide the source moon's warmer yellow shades.
 shutil.copyfile(dst/'MOON.PAL',dst/'PALETTE.BIN')
 (dst/'palette.json').write_text(json.dumps({'rgb':info['palette_rgb'],'modified_unused_slots':list(map(int,info['modified_unused_slots']))},indent=2)+'\n')
 (dst/'ISLAND.EGA').write_bytes(planar(raw));png(dst/'island.png',raw,320,200)
 (dst/'effects-provenance.json').write_text(json.dumps({'base':'ORIGINAL.EGA','added_to_island':'HD-extracted14x14 moon at232,14; assets/moon.json','cloud':'video-derived motion-aligned strip; see research/clouds/tracking.json','sky_mask':'video-verified mountain contour and closed dither notches; assets/mountain-occlusion-evidence.json','shooting_stars':'two video-derived timed keyframe sequences; see research/clouds/meteors.json','island_sha256':hashlib.sha256((dst/'ISLAND.EGA').read_bytes()).hexdigest()},indent=2)+'\n')
 print('Prepared source moon and native mountain matte; video assets preserved.')
if __name__=='__main__':main()
