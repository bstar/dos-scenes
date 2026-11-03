#!/usr/bin/env python3
"""Append editable OPL2 white-noise surf to a saved Furnace232 project.
Keeps original instrument/pattern blocks byte-for-byte; writes a separate file.
"""
import argparse,struct,zlib,math,random,hashlib,json
from pathlib import Path
P=lambda fmt,*x:struct.pack('<'+fmt,*x)
S=lambda x:x.encode()+b'\0'
def block(tag,data):return tag+P('I',len(data))+data
def feature(tag,data):return tag+P('H',len(data))+data
class Reader:
 def __init__(self,b,p=0):self.b=b;self.p=p
 def take(self,n):v=self.b[self.p:self.p+n];assert len(v)==n;self.p+=n;return v
 def unpack(self,f):return struct.unpack('<'+f,self.take(struct.calcsize('<'+f)))
 def string(self):end=self.b.index(0,self.p)+1;return self.take(end-self.p)
def add(source,dest):
 assert source.resolve()!=dest.resolve()
 original=source.read_bytes();b=original if original.startswith(b'-Furnace module-') else zlib.decompress(original)
 version=struct.unpack_from('<H',b,16)[0];assert version==232,version
 oldinfo=struct.unpack_from('<I',b,20)[0];assert b[oldinfo:oldinfo+4]==b'INFO'
 length=struct.unpack_from('<I',b,oldinfo+4)[0];r=Reader(b,oldinfo+8)
 fixed=bytearray(r.take(248));patlen,orders=struct.unpack_from('<HH',fixed,8);ni,nw,ns,np=struct.unpack_from('<HHHI',fixed,14)
 assert fixed[24]==0x90 and not any(fixed[25:56]),'Expected one melodic OPL2 chip'
 fixed[24]=0xa3 # OPL2 rhythm mode: six melodic + five percussion channels
 struct.pack_into('<H',fixed,14,ni+1);struct.pack_into('<I',fixed,20,np+orders*3)
 meta=r.string()+r.string()+r.take(24)
 old_ip=list(r.unpack('I'*ni));old_wp=r.take(nw*4);old_sp=r.take(ns*4);old_pp=list(r.unpack('I'*np))
 orderdata=r.take(9*orders);effects=r.take(9);show=r.take(9);collapse=r.take(9)
 names=[r.string() for _ in range(9)];short=[r.string() for _ in range(9)]
 tail=b[r.p:oldinfo+8+length]
 # Refuse notes on physical melodic channels that drums mode would replace.
 for ptr in old_pp:
  assert b[ptr:ptr+4]==b'PATN','Expected modern pattern encoding'
  ch=b[ptr+9]
  if ch<6:continue
  q=Reader(b,ptr+12);q.string();end=ptr+8+struct.unpack_from('<I',b,ptr+4)[0]
  while q.p<end:
   mask=q.take(1)[0]
   if mask==255:break
   if mask&128:continue
   m1=q.take(1)[0] if mask&32 else 0;m2=q.take(1)[0] if mask&64 else 0
   assert not mask&1,'Saved project has notes on a channel reserved for drums'
   if mask&2:q.take(1)
   if mask&4:q.take(1)
   if mask&8:q.take(1)
   if mask&16:q.take(1)
   q.take((m1&252).bit_count()+m2.bit_count())
 # Re-use existing final pattern break location, so surf respects the music loop.
 # This project ends at global row1038 (the original conversion's loop marker).
 endrow=1038;assert orders==17 and patlen==64
 rng=random.Random(3812);envelope=[0.]*(endrow+1);start=-18
 while start<endrow:
  attack=rng.randint(12,20);decay=rng.randint(32,52);peak=rng.randint(43,59)
  for i in range(attack+decay):
   row=start+i
   if not 0<=row<=endrow:continue
   x=i/attack if i<attack else max(0,1-(i-attack)/decay)
   shape=(.5-.5*math.cos(math.pi*x)) if i<attack else x*x*(3-2*x)
   envelope[row]+=peak*shape
  start+=attack+decay+rng.randint(0,10)
 values=[]
 for row,v in enumerate(envelope):
  # Gentle entry/exit and quiet inter-wave wash; no hard cuts at loop boundary.
  fade=min(1,row/20,max(0,(endrow-row)/24))
  values.append(max(0,min(63,round((3+v)*fade))))
 fm=bytes([0xf4,0,0,0,0])+bytes([1,128+16,15,0,32,8,0,0])+bytes([1,128+63,15,0,32,8,0,0])*3
 ins=block(b'INS2',P('HH',232,32)+feature(b'NA',S('Ocean surf - OP1 TL = level'))+feature(b'FM',fm)+feature(b'LD',P('BHHH',1,1,1,1))+b'EN')
 out=bytearray(b);newins=len(out);out+=ins;new_pp=[]
 for ch in [7,9,10]:
  for order in range(orders):
   data=P('BBH',0,ch,order)+S('Ocean waves' if ch==7 else 'Spare percussion')
   for local in range(patlen):
    row=order*patlen+local
    if ch!=7 or row>endrow:data+=bytes([0]);continue
    if row==0:data+=bytes([7,84,ni,values[row]]) # Pitch overridden by LD: fnum1, effectively DC; snare output is noise
    elif row==endrow:data+=bytes([1,180])
    else:data+=bytes([4,values[row]])
   data+=b'\xff';new_pp.append(len(out));out+=block(b'PATN',data)
 info=bytes(fixed)+meta+P('I'*(ni+1),*(old_ip+[newins]))+old_wp+old_sp+P('I'*(np+len(new_pp)),*(old_pp+new_pp))
 info+=orderdata+bytes(range(orders))*2+effects+bytes([1,1])+show+bytes([1,1])+collapse+bytes(2)
 # Give formerly spare channels their hardware roles.
 names[6:9]=[S('Spare kick'),S('Ocean waves (white noise)'),S('Loop marker / spare tom')]
 info+=b''.join(names+[S('Spare cymbal'),S('Spare hi-hat')])+b''.join(short+[S('CYM'),S('SURF')])+tail
 newinfo=len(out);out+=block(b'INFO',info);struct.pack_into('<I',out,20,newinfo)
 dest.write_bytes(zlib.compress(out,9))
 proof={'source':str(source),'source_sha256':hashlib.sha256(original).hexdigest(),'output':str(dest),'original_instrument_blocks_unchanged':ni,'original_pattern_blocks_unchanged':np,'wave_instrument':ni,'wave_channel':8,'rhythm_mode':True,'wave_peak_instrument_TL':16,'wave_volume_min':min(values),'wave_volume_max':max(values),'notes':'OPL2 snare noise with near-zero phase frequency, irregular slow volume swells. Instrument OP1 TL controls the surf level.'}
 dest.with_suffix('.json').write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps(proof,indent=2))
if __name__=='__main__':
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('source',type=Path);ap.add_argument('output',type=Path);a=ap.parse_args();add(a.source,a.output)
