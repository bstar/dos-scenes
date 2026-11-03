"""Small, documented scene-pack serializers. All integers are little endian."""
import struct
P=struct.pack
PALETTE=[(0,0,0),(0,0,170),(0,170,0),(0,170,170),(170,0,0),(170,0,170),(170,85,0),(170,170,170),(85,85,85),(85,85,255),(85,255,85),(85,255,255),(255,85,85),(255,85,255),(255,255,85),(255,255,255)]
def planar(pixels):
 out=bytearray(32000)
 for y in range(200):
  for x in range(320):
   c=pixels[y*320+x]
   for plane in range(4):
    if c&(1<<plane):out[plane*8000+y*40+x//8]|=128>>(x%8)
 return bytes(out)
def details(lights=(),routes=(),ripples=()):
 out=bytearray(b'DSD1'+P('<3H',len(lights),len(routes),len(ripples)))
 for light in lights:out+=P('<5H2B',*light,0)
 for r in routes:
  points=r['points'];out+=P('<6H2BH',len(points),r['ticks'],r['pause'],r['start'],r['salt'],r['cutoff'],r.get('body',6),r.get('head',7),r.get('mask',65535))
  for x,y in points:out+=P('<2H',x,y)
 for ripple in ripples:out+=P('<8H2B',*ripple)
 if len(out)>60000:raise ValueError('DETAILS.BIN exceeds the real-mode file limit')
 return out
