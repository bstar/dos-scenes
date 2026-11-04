"""Independent scene-pack compositor for real DOS VRAM readback."""
import struct,math
from pathlib import Path
U=lambda b,o:struct.unpack_from('<H',b,o)[0]
def decode(b):
 return [sum(((b[p*8000+y*40+x//8]>>(7-x%8))&1)<<p for p in range(4)) for y in range(200) for x in range(320)]
def compose(directory,t,frame,ambient=True):
 d=Path(directory);base=decode((d/'SCENE.EGA').read_bytes());out=base.copy()
 opts={}
 for line in (d/'SCENE.CFG').read_text().splitlines():
  pair=line.split(None,1)
  if len(pair)==2:opts[pair[0]]=pair[1]
 sky=(d/'SKY.MSK').read_bytes() if (d/'SKY.MSK').exists() else bytes(8000)
 def allowed(x,y):return 0<=x<320 and 0<=y<200 and sky[y*40+x//8]&(128>>(x%8))
 def pixel(x,y,c):
  if 0<=x<320 and 0<=y<200:out[y*320+x]=c
 if (d/'TWINKLE.BIN').exists():
  b=(d/'TWINKLE.BIN').read_bytes();count=struct.unpack_from('<H',b,4)[0]
  for i in range(count):
   x,y,period,phase,duration,source,dim=struct.unpack_from('<5H2B',b,6+i*12)
   if allowed(x,y) and base[y*320+x]==source and (t+phase)%period<duration:pixel(x,y,dim)
 if (d/'MOON.BIN').exists():
  b=(d/'MOON.BIN').read_bytes();x,y,w,h=struct.unpack_from('<4H',b);duration=int(opts.get('MOON_SECONDS',3600))*560
  if t<duration:
   i,rem=divmod(t*32,duration)
   arc=[(round(256*math.sin(i*math.pi/64)),round(256*(1-math.cos(i*math.pi/64)))) for i in range(33)]
   x+=int(int(opts.get('MOON_DX',88))*(arc[i][0]+(arc[i+1][0]-arc[i][0])*rem//duration)/256)
   y+=int(int(opts.get('MOON_DY',80))*(arc[i][1]+(arc[i+1][1]-arc[i][1])*rem//duration)/256)
   for yy in range(h):
    for xx in range(w):
     c=b[8+yy*w+xx]
     if c!=255 and allowed(x+xx,y+yy):pixel(x+xx,y+yy,c)
 if (d/'CLOUD.BIN').exists():
  b=(d/'CLOUD.BIN').read_bytes();w,h,left,top=struct.unpack_from('<HHhH',b)
  spacing,mul,div,cycle=(870,41,6244,132508)
  if (d/'CLOUD.MOT').exists():spacing,mul,div,cycle=struct.unpack('<3HI',(d/'CLOUD.MOT').read_bytes())
  left=(left-(t%cycle)*mul//div)%spacing
  if left>=320:left-=spacing
  for y in range(h):
   for x in range(w):
    c=b[8+y*w+x]
    if c!=255 and allowed(left+x,top+y):pixel(left+x,top+y,c)
 if (d/'FIRE.BIN').exists():
  b=(d/'FIRE.BIN').read_bytes();w,h,n=struct.unpack_from('<3H',b);fx=int(opts.get('FIRE_X',0));fy=int(opts.get('FIRE_Y',0))
  for y in range(h):
   for x in range(w):pixel(fx+x,fy+y,b[6+(frame%n)*w*h+y*w+x])
 for name in ['STAR1.BIN','STAR2.BIN']:
  if not (d/name).exists():continue
  b=(d/name).read_bytes();n,period,phase=struct.unpack_from('<3H',b);at=t%period-phase;off=6
  if at<0:continue
  for _ in range(n):
   x,y,w,h,hold=struct.unpack_from('<hh3H',b,off);off+=10
   if at<hold:
    for yy in range(h):
     for xx in range(w):
      c=b[off+yy*w+xx]
      if c!=255 and allowed(x+xx,y+yy):pixel(x+xx,y+yy,c)
    break
   at-=hold;off+=w*h
 if ambient and (d/'DETAILS.BIN').exists():
  b=(d/'DETAILS.BIN').read_bytes();lights,routes,ripples=struct.unpack_from('<3H',b,4);off=10
  for _ in range(lights):
   x,y,period,phase,duration,color,_=struct.unpack_from('<5H2B',b,off);off+=12
   if (t+phase)%period<duration:pixel(x,y,color)
  for _ in range(routes):
   n,rate,pause,start,salt,cutoff,body,head,mask=struct.unpack_from('<6H2BH',b,off);off+=16
   trip,step=divmod(t//rate+start,n+pause)
   if step<n:
    mix=(trip*25173+salt*13849+173)&65535;mix^=mix>>7;mix=mix*40503&65535;mix^=mix>>9
    if mix&1:step=n-1-step
    x,y=struct.unpack_from('<2H',b,off+step*4)
    if mask&(1<<base[y*320+x]):pixel(x,y,body if y>cutoff else head)
    if y>cutoff and mask&(1<<base[(y-1)*320+x]):pixel(x,y-1,head)
   off+=4*n
  for _ in range(ripples):
   x,y,w,rate,start,period,duty,active,c1,c2=struct.unpack_from('<8H2B',b,off);off+=18;phase=(t//rate+start)%period
   if phase%duty>=active:continue
   x+=phase%w;c=base[y*320+x]
   if c in (c1,c2):pixel(x,y,c2 if c==c1 else c1)
 return out
