#!/usr/bin/env python3
"""Recover the static moon from registered HD cell centers, without resampling."""
import argparse,hashlib,json,struct
from pathlib import Path
import cv2,numpy as np
from extract_assets import PALETTE
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'assets';REVIEW=ROOT/'research/clouds'
def main():
 p=argparse.ArgumentParser();p.add_argument('opening_1080p');a=p.parse_args()
 palette=np.array(PALETTE,np.int32)
 b=np.frombuffer((OUT/'ORIGINAL.EGA').read_bytes(),np.uint8).reshape(4,200,40)
 original=sum(np.unpackbits(b[k],axis=1)*(1<<k) for k in range(4))
 def labels(rgb,pal=palette):return np.argmin(np.sum((rgb.astype(np.int32)[...,None,:]-pal)**2,axis=-1),axis=-1).astype('uint8')
 times=[70,75,80,85,90,95,100];cap=cv2.VideoCapture(a.opening_1080p);rgbs=[];indexed=[]
 for t in times:
  cap.set(cv2.CAP_PROP_POS_MSEC,t*1000);ok,f=cap.read();assert ok and f.shape[:2]==(1080,1920)
  rgb=cv2.cvtColor(f,cv2.COLOR_BGR2RGB)[82:210:5,1292:1430:5]
  rgbs.append(rgb);indexed.append(labels(rgb))
 cap.release();indexed=np.array(indexed)
 mode=np.apply_along_axis(lambda v:np.bincount(v,minlength=16).argmax(),0,indexed)
 mask=mode!=original[8:34,226:254]
 count,lab,stats,_=cv2.connectedComponentsWithStats(mask.astype('uint8'),8)
 chosen=max(range(1,count),key=lambda k:stats[k,4]);mask=lab==chosen
 assert all(np.array_equal(frame[mask],mode[mask]) for frame in indexed),'Moon is not stable across clear frames'
 yy,xx=np.where(mask);x0,x1=xx.min(),xx.max()+1;y0,y1=yy.min(),yy.max()+1
 x,y,w,h=226+int(x0),8+int(y0),int(x1-x0),int(y1-y0)
 rgb=rgbs[times.index(90)][y0:y1,x0:x1];alpha=mask[y0:y1,x0:x1]
 used=set(original.ravel())|set((OUT/'FIRE.BIN').read_bytes()[6:])|set((OUT/'CLOUD.BIN').read_bytes()[8:])-{255}
 for name in ['STAR1.BIN','STAR2.BIN']:
  d=(OUT/name).read_bytes();n,_,_=struct.unpack_from('<HHH',d);off=6
  for i in range(n):
   _,_,ww,hh,_=struct.unpack_from('<hhHHH',d,off);off+=10;used|=set(d[off:off+ww*hh])-{255};off+=ww*hh
 free=sorted(set(range(16))-used);assert free==[2,4,10,13],free
 pixels=rgb[alpha].astype(np.int32);fixed=palette[sorted(used)]
 candidates=np.array([(r,g,b) for r in range(0,256,85) for g in range(0,256,85) for b in range(0,256,85)],np.int32)
 error=np.min(np.sum((pixels[:,None,:]-fixed)**2,axis=-1),axis=1)
 assignments={}
 for slot in free:
  dist=np.sum((pixels[:,None,:]-candidates)**2,axis=-1)
  gain=np.sum(error[:,None]-np.minimum(error[:,None],dist),axis=0)
  best=int(gain.argmax())
  if gain[best]<=0:break
  palette[slot]=candidates[best];error=np.minimum(error,dist[:,best]);assignments[slot]=palette[slot].tolist()
 index=labels(rgb,palette);index[~alpha]=255
 (OUT/'MOON.BIN').write_bytes(struct.pack('<HHHH',x,y,w,h)+index.tobytes())
 def ega(c):return sum((((v//85)&1)<<(5-i))|((((v//85)>>1)&1)<<(2-i)) for i,v in enumerate(c))
 (OUT/'MOON.PAL').write_bytes(bytes(ega(c) for c in palette))
 info={'source':'https://www.youtube.com/watch?v=ikaqus5_QIg','source_sha256':hashlib.sha256(Path(a.opening_1080p).read_bytes()).hexdigest(),'sample_seconds':times,'sample_hd_origin':[160,40],'scale':5,'position':[x,y],'size':[w,h],'opaque_pixels':int(alpha.sum()),'stable_across_all_samples':True,'selected_rgb_frame_second':90,'palette_rgb':palette.tolist(),'modified_unused_slots':assignments,'layer':'background; video clouds cross in front of lower moon at18:40','method':'direct HD cell samples; connected difference from original scene; no RGB averaging'}
 (OUT/'moon.json').write_text(json.dumps(info,indent=2)+'\n')
 cv2.imwrite(str(REVIEW/'moon-source.png'),cv2.cvtColor(np.dstack([rgb,alpha.astype('uint8')*255]),cv2.COLOR_RGBA2BGRA))
 rendered=palette[index.clip(0,15)].astype('uint8');rendered[~alpha]=0
 cv2.imwrite(str(OUT/'moon.png'),cv2.cvtColor(np.dstack([rendered,alpha.astype('uint8')*255]),cv2.COLOR_RGBA2BGRA))
 print('Moon:',x,y,w,h,'opaque',alpha.sum(),'palette',assignments)
if __name__=='__main__':main()
