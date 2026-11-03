#!/usr/bin/env python3
"""Generate an original, redistributable night-coast scene and simple OPL2 motif."""
from pathlib import Path
import argparse,random,struct,math
from scene_format import planar,details
ROOT=Path(__file__).resolve().parents[1]
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=ROOT/'build/scenes/demo');args=ap.parse_args();d=args.output;d.mkdir(parents=True,exist_ok=True)
 rng=random.Random(1027);p=[1]*64000;sky=bytearray(8000)
 horizon=[145 if x>95 else 125+x//5 for x in range(320)]
 for y in range(200):
  for x in range(320):
   if y<horizon[x]:sky[y*40+x//8]|=128>>(x%8)
   else:p[y*320+x]=9 if y>150 and ((x*7+y*13)%47<2) else 1
 for _ in range(150):
  x=rng.randrange(320);y=rng.randrange(120);p[y*320+x]=rng.choice([9,11,15])
 for y in range(125,200):
  for x in range(max(0,95-(y-125)*2)):p[y*320+x]=0
 for y in range(88,137):
  for x in range(44,51):p[y*320+x]=8 if x==44 else 0
 for y in range(84,89):
  for x in range(42,53):p[y*320+x]=14 if y==86 else 8
 for x in range(10,70):p[146*320+x]=8 if x%2 else 1
 p[136*320+60]=14
 (d/'SCENE.EGA').write_bytes(planar(p));(d/'SKY.MSK').write_bytes(sky)
 codes=[0,1,2,3,4,5,20,7,56,57,58,59,60,61,62,63];(d/'PALETTE.BIN').write_bytes(bytes(codes))
 moon=bytearray([255]*196)
 for y in range(14):
  for x in range(14):
   if (x-6.5)**2+(y-6.5)**2<45 and (x-9)**2+(y-5)**2>32:moon[y*14+x]=15
 (d/'MOON.BIN').write_bytes(struct.pack('<4H',230,22,14,14)+moon)
 cloud=bytearray([255]*1920)
 for y in range(20):
  for x in range(96):
   if ((x-47)/46)**2+((y-10)/8)**2<1:cloud[y*96+x]=9 if (x+y)&1 else 1
 (d/'CLOUD.BIN').write_bytes(struct.pack('<HHhH',96,20,158,38)+cloud)
 route=[(x,145) for x in range(12,68)]
 (d/'DETAILS.BIN').write_bytes(details(lights=[(60,136,50000,8000,500,6)],routes=[dict(points=route,ticks=330,pause=30,start=5,salt=9,cutoff=0)],ripples=[(110,175,20,300,1,360,9,6,1,9),(220,186,28,320,9,360,9,6,1,9)]))
 (d/'SCENE.CFG').write_bytes(b'NAME Night Coast\r\nMOON_SECONDS 3600\r\nMOON_DX 90\r\nMOON_DY 70\r\n')
 events=[]
 def w(delay,reg,value):events.append(struct.pack('<HBB',delay,reg,value))
 for reg,val in [(1,32),(0x20,1),(0x23,1),(0x40,30),(0x43,14),(0x60,0xf2),(0x63,0xf2),(0x80,0x75),(0x83,0x75),(0xc0,0)]:w(0,reg,val)
 for note in [60,64,67,69,67,64,62,60]:
  hz=440*2**((note-69)/12);block=4;fnum=round(hz*2**(20-block)/49716)
  w(0,0xa0,fnum&255);w(0,0xb0,32|(block<<2)|(fnum>>8));w(210,0xb0,(block<<2)|(fnum>>8));w(70,0x43,14)
 w(140,0xb0,0);(d/'DEMO.OPL').write_bytes(b''.join(events));(d/'PLAYLIST.CFG').write_bytes(b'DEMO.OPL\r\n')
 print(d)
if __name__=='__main__':main()
