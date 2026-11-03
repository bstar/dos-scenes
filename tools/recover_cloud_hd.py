#!/usr/bin/env python3
"""Recover cloud pixel cells from registered1080p frames, without RGB averaging.
The original320x200 artwork is at(160,40), scaled exactly5x in the video.
Samples are taken at cell centers after tracking the moving layer's own grid.
"""
import argparse,json,struct,hashlib
from pathlib import Path
from fractions import Fraction
import cv2,numpy as np
from extract_assets import PALETTE
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'assets';REVIEW=ROOT/'research/clouds'
PAL=np.array(PALETTE,np.int32)
def labels(rgb):return np.argmin(np.sum((rgb.astype(np.int32)[...,None,:]-PAL)**2,axis=-1),axis=-1).astype('uint8')
def load(path):
 c=cv2.VideoCapture(str(path));frames=[]
 for t in range(0,180,2):
  c.set(cv2.CAP_PROP_POS_MSEC,t*1000);ok,a=c.read();assert ok,(path,t)
  assert a.shape[:2]==(1080,1920)
  frames.append(cv2.cvtColor(a[115:465],cv2.COLOR_BGR2RGB))
 c.release();return np.array(frames)
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('opening');ap.add_argument('minute17');args=ap.parse_args()
 OUT.mkdir(parents=True,exist_ok=True);REVIEW.mkdir(parents=True,exist_ok=True)
 source_hashes=[hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in [args.opening,args.minute17]]
 prior=json.loads((REVIEW/'hd-recovery.json').read_text()) if (REVIEW/'hd-recovery.json').exists() else {}
 same_sources=[v.get('sha256') for v in prior.get('source_files',[])]==source_hashes
 sets=[]
 for name,path in [('opening',args.opening),('minute17',args.minute17)]:
  key=source_hashes[0 if name=='opening' else 1][:12]
  cache=Path('/tmp/cloud-hd-cells-v2-'+name+'-'+key+'.npy')
  legacy=Path('/tmp/cloud-hd-cells-v2-'+name+'.npy')
  if not cache.exists() and legacy.exists() and same_sources:
   import os
   os.link(legacy,cache)
  if cache.exists():a=np.load(cache)
  else:a=load(path);np.save(cache,a)
  sets.append(a)
 print('Loaded HD cloud bands',flush=True)
 data=np.frombuffer((OUT/'ORIGINAL.EGA').read_bytes(),np.uint8).reshape(4,200,40)
 original=sum(np.unpackbits(data[k],axis=1)*(1<<k) for k in range(4))
 n,lab,stats,_=cv2.connectedComponentsWithStats(np.isin(original,[0,8,6,14]).astype('uint8'),8)
 contour=np.argmax(lab==max(range(1,n),key=lambda k:stats[k,4]),axis=0)
 # A clean BG frame in correct native coordinates; original matches98.4% exactly.
 c=cv2.VideoCapture(args.opening);c.set(cv2.CAP_PROP_POS_MSEC,90000);ok,frame=c.read();assert ok
 bgfull=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB);c.release();bgband=bgfull[115:465]
 bg_native=labels(bgfull[42:1040:5,162:1760:5])
 native_mask=np.indices((200,320))[0]<contour[None,:]-2
 # Safe sky for tracking: extended side padding is sky in this band; terrain is excluded.
 safe=np.ones((350,1920),np.uint8)
 for x in range(320):safe[max(0,(int(contour[x])-15-2)*5):,160+x*5:165+x*5]=0
 sift=cv2.SIFT_create(nfeatures=6000,contrastThreshold=.015,edgeThreshold=15)
 def feat(im):
  diff=np.linalg.norm(im.astype(float)-bgband.astype(float),axis=2)>45
  mask=safe.astype('uint8')*255
  return sift.detectAndCompute(cv2.cvtColor(im,cv2.COLOR_RGB2GRAY),mask)
 previous_path=REVIEW/'hd-recovery.json'
 if previous_path.exists() and same_sources:
  previous=json.loads(previous_path.read_text());tracks=previous['tracks']
  hd_speed=previous['speed_native']*5;hd_period=previous['period_native']*5;hd_phase=previous['phase_hd']
  print('Reusing verified HD feature tracks',len(tracks),flush=True)
 else:
  anchor=feat(sets[0][0]);matcher=cv2.BFMatcher()
  def match(ref,cur,expected):
   kr,dr=ref;k,d=cur
   if d is None or dr is None:return None
   ms=matcher.knnMatch(dr,d,k=2)
   ds=np.array([np.array(k[a.trainIdx].pt)-kr[a.queryIdx].pt for pair in ms if len(pair)==2 for a,b in [pair] if a.distance<.8*b.distance])
   if len(ds)<5:return None
   ds=ds[(abs(ds[:,1])<2.5)&(abs(ds[:,0]-expected)<15)]
   if len(ds)<5:return None
   bins=np.round(ds[:,0]).astype(int);v=np.bincount(bins+3000,minlength=6000).argmax()-3000
   good=ds[abs(ds[:,0]-v)<2]
   if len(good)<5:return None
   return float(np.median(good[:,0])),len(good)
  v=18.38;P=4350.0
  second=feat(sets[1][50]);link=match(anchor,second,-v*1120+P*5);assert link, 'Cannot register second cloud pass'
  print('Second anchor HD translation',link,flush=True)
  tracks=[];features=[]
  for j,images in enumerate(sets):
   fs=[]
   for i,im in enumerate(images):
    t=i*2;f=feat(im);fs.append(f);expected=-v*(t+j*1020)+P*(0 if j==0 and t<90 else(1 if j==0 else 5));m=match(anchor,f,expected)
    if m is None:
     m2=match(second,f,expected-link[0])
     if m2 is not None:m=(m2[0]+link[0],m2[1])
    if m is not None:
     expected=-v*(t+j*1020)+P*(0 if j==0 and t<90 else(1 if j==0 else 5))
     if abs(m[0]-expected)<12:tracks.append([j,t,m[0],m[1]])
   features.append(fs)
  A=np.array([[-(t+j*1020),0 if j==0 and t<90 else(1 if j==0 else 5),1] for j,t,x,n in tracks]);b=np.array([x for j,t,x,n in tracks])
  hd_speed,hd_period,hd_phase=np.linalg.lstsq(A,b,rcond=None)[0]
  print('HD fitted',hd_speed,hd_period,hd_phase,'tracks',len(tracks),flush=True)
 # World grid is the cloud grid in frame0; no interpolation, no RGB median.
 lo,hi,top,bottom=-170,250,18,84;w=hi-lo;h=bottom-top;U=np.arange(lo,hi);Y=np.arange(top,bottom)
 counts=np.zeros((h,w,16),np.uint16);different=np.zeros_like(counts)
 best=np.full((h,w,16),1e9,np.float32);chosen=np.zeros((h,w,16,3),np.uint8)
 nobs=np.zeros((h,w),np.uint16);phase_report=[]
 for j,images in enumerate(sets):
  for i,im in enumerate(images):
   t=i*2;cycle=0 if j==0 and t<90 else(1 if j==0 else 5)
   predicted=-hd_speed*(t+j*1020)+hd_period*cycle+hd_phase
   found=next((x for jj,tt,x,n in tracks if jj==j and tt==t),None)
   if found is not None:predicted=found
   # Determine the cloud's5px grid phase from its internal high-contrast edges.
   diff=np.linalg.norm(im.astype(float)-bgband.astype(float),axis=2)>45
   gray=cv2.cvtColor(im,cv2.COLOR_RGB2GRAY).astype(float)
   dx=abs(np.diff(gray,axis=1));eligible=(safe[:,:-1]>0)&diff[:,:-1]&(dx>30)
   scores=np.array([float((dx*eligible)[:,k::5].sum()) for k in range(5)])
   q=(int(scores.argmax())+1)%5
   shift=int(q+5*round((predicted-q)/5))
   xx=162+5*U+shift;validx=(xx>=0)&(xx<1920)
   sx=np.clip(xx,0,1919);sy=42+5*Y-115
   rgb=im[sy[:,None],sx[None,:]];idx=labels(rgb)
   native_x=np.floor_divide(sx-160,5);inbase=(native_x>=0)&(native_x<320)
   nx=np.clip(native_x,0,319)
   valid=validx[None,:]&inbase[None,:]&native_mask[Y[:,None],nx[None,:]]&(bg_native[Y[:,None],nx[None,:]]==original[Y[:,None],nx[None,:]])
   background=bg_native[Y[:,None],nx[None,:]]
   nobs+=valid
   error=np.sum((rgb.astype(np.int32)-PAL[idx])**2,axis=2)
   for color in [1,9]:
    m=valid&(idx==color);counts[:,:,color]+=m;different[:,:,color]+=m&(background!=color)
    improve=m&(error<best[:,:,color]);best[:,:,color][improve]=error[improve];chosen[:,:,color][improve]=rgb[improve]
   phase_report.append([j,t,shift,q,float(scores.max()/max(1,scores.sum()))])
 mode=np.where(counts[:,:,9]>counts[:,:,1],9,1);iy,ix=np.indices((h,w));votes=counts[iy,ix,mode];positive=different[iy,ix,mode]
 stable=votes/np.maximum(nobs,1)
 alpha=(nobs>=6)&(stable>.92)&(positive>=2)
 # Recover single-pixel checker holes using observed stable dark cells only.
 for _ in range(2):
  neighbors=cv2.filter2D(alpha.astype(np.uint8),-1,np.array([[0,1,0],[1,0,1],[0,1,0]],np.uint8))
  alpha|=(neighbors>=3)&(mode==1)&(stable>.92)&(nobs>=6)
 # Remove tiny detached moving-glitter/compression specks, retain actual wisps.
 n,lab,stats,_=cv2.connectedComponentsWithStats(alpha.astype('uint8'),8)
 for k in range(1,n):
  if stats[k,4]<3 and not np.any((lab==k)&(stable>.995)&(positive>=3)&(nobs>=12)):alpha[lab==k]=False
 yy,xx=np.where(alpha);x0,x1=xx.min(),xx.max()+1;y0,y1=yy.min(),yy.max()+1
 idx=mode[y0:y1,x0:x1].astype('uint8');mask=alpha[y0:y1,x0:x1];idx[~mask]=255
 rgb=chosen[iy,ix,mode][y0:y1,x0:x1];rgb[~mask]=0
 origin=lo+int(x0);ctop=top+int(y0);ch,cw=idx.shape
 (OUT/'CLOUD.BIN').write_bytes(struct.pack('<HHhH',cw,ch,origin,ctop)+idx.tobytes())
 cv2.imwrite(str(REVIEW/'cloud-hd-extracted.png'),cv2.cvtColor(np.dstack([rgb,mask.astype('uint8')*255]),cv2.COLOR_RGBA2BGRA))
 display=PAL[np.where(idx==255,0,idx)].astype('uint8');cv2.imwrite(str(OUT/'cloud.png'),cv2.cvtColor(display,cv2.COLOR_RGB2BGR))
 print('Cloud',origin,ctop,cw,ch,'opaque',mask.sum(),'mean vote',stable[y0:y1,x0:x1][mask].mean(),flush=True)
 report={'registration':{'original_origin_hd':[160,40],'scale':5,'sample_centers_hd':[162,42]},'speed_native':hd_speed/5,'period_native':hd_period/5,'phase_hd':hd_phase,'tracks':tracks,'frame_grid_phase':phase_report,'crop':[origin,ctop,cw,ch],'mean_modal_consistency':float(stable[y0:y1,x0:x1][mask].mean()),'palette_indices':[1,9],'method':'observed palette-cell votes; selected actual source RGB per cell; no RGB averaging or rescaling','source_files':[{'sha256':hashlib.sha256(Path(p).read_bytes()).hexdigest()} for p in [args.opening,args.minute17]]}
 from finish_hd_assets import finish
 finish(sets,bgfull,original,contour,report,args.opening)
 (REVIEW/'hd-recovery.json').write_text(json.dumps(report,indent=2)+'\n')
 import shutil
 shutil.copyfile(REVIEW/'cloud-hd-extracted.png',REVIEW/'cloud-extracted.png')
 if (OUT/'MOON.BIN').exists():
  from prepare_effects import main as prepare
  prepare()
 np.savez('/tmp/cloud-hd-votes.npz',counts=counts,nobs=nobs,stable=stable,alpha=alpha,mode=mode,positive=positive)
if __name__=='__main__':main()
