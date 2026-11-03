#!/usr/bin/env python3
"""Add an independent steady OPL2 ocean bed to a saved rhythm-mode project."""
import argparse,struct,zlib,json,hashlib,math
from pathlib import Path
from add_ocean_furnace import Reader,P,S,block,feature

def add(source,dest,solo=False):
 note=0
 raw=source.read_bytes();b=raw if raw.startswith(b'-Furnace module-') else zlib.decompress(raw);out=bytearray(b)
 assert struct.unpack_from('<H',b,16)[0]==232
 ip=struct.unpack_from('<I',b,20)[0];size=struct.unpack_from('<I',b,ip+4)[0];r=Reader(b,ip+8);fixed=bytearray(r.take(248));assert fixed[24]==0xa3
 ni,nw,ns,np=struct.unpack_from('<HHHI',fixed,14);patlen,orders=struct.unpack_from('<HH',fixed,8);assert (patlen,orders)==(64,17)
 meta=r.string()+r.string()+r.take(24);ins=list(r.unpack('I'*ni));wp=r.take(nw*4);sp=r.take(ns*4);pats=list(r.unpack('I'*np));od=r.take(11*orders);ef=r.take(11);show=r.take(11);collapse=r.take(11);names=[r.string() for _ in range(11)];short=[r.string() for _ in range(11)];tail=b[r.p:ip+8+size]
 # Fixed fnum1 suppresses the pitched component. Normal OPL instrument type updates only the hi-hat operator; the snare patch and level remain independent. OPLL preset16 activates fixed drum frequency handling in Furnace.
 fm=bytes([0x32,0,0,16,0])+bytes([0,128+24,15,0,32,8,0,0])+bytes([0,128+63,15,0,0,8,0,0])
 newins=len(out);out+=block(b'INS2',P('HH',232,14)+feature(b'NA',S('Ocean bed - OP1 TL = level'))+feature(b'FM',fm)+feature(b'LD',P('BHHH',1,1,1,1))+b'EN');ins.append(newins)
 if solo:
  # Diagnostic only: mute music and crashing surf by replacing note patterns.
  for j,p in enumerate(pats):
   if b[p+9] in [0,1,2,3,7]:
    q=Reader(b,p+8);hdr=q.take(4);name=q.string();pats[j]=len(out);out+=block(b'PATN',hdr+name+b'\xff')
 end=1038 if not solo else 160
 for order in range(orders):
  data=P('BBH',0,10,order)+S('Steady low ocean bed')
  for local in range(64):
   row=order*64+local
   if row>end:data+=bytes([0]);continue
   fade=min(1,row/32,max(0,(end-row)/24))
   volume=round((48+.6*math.sin(row*.024)+.35*math.sin(row*.009))*fade)
   if row==0:data+=bytes([7,note,ni,0])
   elif row==end:data+=bytes([1,180])
   else:data+=bytes([4,volume])
   if solo and row==end:
    # Add final pattern break after noise release in same row.
    data=data[:-2]+bytes([25,180,0x0d,0])
  data+=b'\xff';pats.append(len(out));out+=block(b'PATN',data)
 struct.pack_into('<H',fixed,14,len(ins));struct.pack_into('<I',fixed,20,len(pats))
 names[10]=S('Ocean bed (steady noise)');short[10]=S('BED')
 info=bytes(fixed)+meta+P('I'*len(ins),*ins)+wp+sp+P('I'*len(pats),*pats)+od+ef+show+collapse+b''.join(names)+b''.join(short)+tail
 newinfo=len(out);out+=block(b'INFO',info);struct.pack_into('<I',out,20,newinfo);dest.write_bytes(zlib.compress(out,9))
 return {'source':str(source),'source_sha256':hashlib.sha256(raw).hexdigest(),'output':str(dest),'bed_instrument':ni,'bed_channel':11,'wave_channel':8,'noise_source':'OPL2 hi-hat random noise at fixed fnum1','level_control':'OP1 TL','bed_volume_center':48,'bed_volume_variation_steps':2,'keeps_crashing_surf':not solo}
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args();r=add(a.source,a.output);a.output.with_suffix('.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
