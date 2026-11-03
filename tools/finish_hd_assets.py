"""Finish motion, native occlusion and meteor assets on the registered HD grid."""
import json,struct
from pathlib import Path
from fractions import Fraction
import cv2,numpy as np
from extract_assets import PALETTE
from refine_mountain import write_outputs
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'assets';REVIEW=ROOT/'research/clouds'
PAL=np.array(PALETTE,np.int32)
def labels(rgb):return np.argmin(np.sum((rgb.astype(np.int32)[...,None,:]-PAL)**2,axis=-1),axis=-1).astype('uint8')
def finish(sets,bgfull,original,contour,report,opening):
 rate=1193182/2131;speed=report['speed_native'];spacing=round(report['period_native']);ratio=Fraction(speed/rate).limit_denominator(8000);cycle=round(report['period_native']/speed*rate)
 (OUT/'CLOUD.MOT').write_bytes(struct.pack('<HHHI',spacing,ratio.numerator,ratio.denominator,cycle))
 motion={'spacing':spacing,'numerator':ratio.numerator,'denominator':ratio.denominator,'period_ticks':cycle,'rate_hz':rate}
 (OUT/'cloud-motion.json').write_text(json.dumps(motion,indent=2)+'\n')
 def ega(c):return sum((((v//85)&1)<<(5-i))|((((v//85)>>1)&1)<<(2-i)) for i,v in enumerate(c))
 (OUT/'PALETTE.BIN').write_bytes(bytes(ega(c) for c in PAL));(OUT/'palette.json').write_text(json.dumps({'rgb':PAL.tolist(),'modified_unused_slots':[]},indent=2)+'\n')
 cloud=(OUT/'CLOUD.BIN').read_bytes();w,h,left,top=struct.unpack_from('<HHhH',cloud);idx=np.frombuffer(cloud[8:],np.uint8).reshape(h,w)
 Y=np.arange(top,top+h);X=np.arange(320);bg=labels(bgfull[42:1040:5,162:1760:5]);covered=np.zeros((200,320));fixed=covered.copy();moving=covered.copy()
 band=(Y[:,None]>=contour[None,:]-8)&(Y[:,None]<contour[None,:]+8)
 for j,t,shift,q,confidence in report['frame_grid_phase']:
  im=sets[j][t//2];actual=labels(im[(42+5*Y-115)[:,None],(162+5*X)[None,:]])
  u=np.floor_divide(2+5*X-shift,5)-left;validx=(u>=0)&(u<w);u=np.clip(u,0,w-1)
  expected=idx[:,u];valid=(expected!=255)&validx[None,:]&band&(expected!=bg[Y])&(bg[Y]==original[Y])
  covered[Y]+=valid;fixed[Y]+=valid*(actual==original[Y]);moving[Y]+=valid*(actual==expected)
 terrain=(covered>=6)&(fixed>=covered*.9);knownsky=(covered>=6)&(moving>=covered*.9)
 corrected=contour.copy()
 for x in range(320):
  y=np.where(terrain[:,x])[0]
  if len(y):corrected[x]=min(corrected[x],y.min())
 before=corrected.copy()
 for x in range(1,319):
  candidate=min(before[x],max(before[x-1],before[x+1]))
  if top<=candidate<before[x]<=top+h and not knownsky[candidate:before[x],x].any():corrected[x]=candidate
 changes=[{'x':x,'y':y,'observations':int(covered[y,x]),'stationary':int(fixed[y,x])} for x in range(320) for y in range(corrected[x],contour[x])]
 evidence={'method':'registered5x HD pixel observations under moving clouds, plus one-column dither closure unless HD proves sky','reference_intervals':[[0,180],[1020,1200]],'native_contour_before':contour.tolist(),'corrected_pixels':changes,'stationary_terrain_pixels':[[int(x),int(y)] for y,x in zip(*np.where(terrain))],'registration':report['registration']}
 write_outputs(corrected,evidence)
 cap=cv2.VideoCapture(opening);sequences=[]
 for n,start,period,rx,rw in [(1,24.533333,61.2,0,85),(2,25.933333,46.2,240,80)]:
  blob=bytearray(struct.pack('<HHH',10,round(period*rate),round(start*rate)));tiles=[]
  for k in range(10):
   cap.set(cv2.CAP_PROP_POS_MSEC,(start+.1+k*.2)*1000);ok,f=cap.read();assert ok
   rgb=cv2.cvtColor(f,cv2.COLOR_BGR2RGB)[42:1040:5,162:1760:5]
   region=rgb[:35,rx:rx+rw];back=bgfull[42:1040:5,162:1760:5][:35,rx:rx+rw]
   d=region.astype(float)-back;mask=(np.linalg.norm(d,axis=2)>35)&(d[:,:,1]>18)
   yy,xx=np.indices(mask.shape)
   # Transform the actual flight corridor into the registered original viewport.
   fullx=xx+rx;oldx=(fullx+32)/1.2
   corridor=oldx if n==1 else oldx-240
   mask&=abs(yy-(corridor*.32-4))<9
   count,lab,stats,_=cv2.connectedComponentsWithStats(mask.astype('uint8'),8);main=np.zeros_like(mask)
   for z in range(1,count):
    if stats[z,4]>=3:main[lab==z]=True
   ys,xs=np.where(main)
   if len(xs):mask&=(xx>=xs.min()-10)&(xx<=xs.max()+5)
   else:mask[:]=False
   ys,xs=np.where(mask)
   if len(xs):
    x0,x1=xs.min(),xs.max()+1;y0,y1=ys.min(),ys.max()+1;pix=labels(region[y0:y1,x0:x1]);pix[~mask[y0:y1,x0:x1]]=255;hh,ww=pix.shape;xx0=rx+x0;yy0=y0
   else:xx0=yy0=0;ww=hh=1;pix=np.array([[255]],np.uint8)
   blob+=struct.pack('<hhHHH',xx0,yy0,ww,hh,112)+pix.tobytes()
   tile=np.zeros_like(region);tile[mask]=region[mask];tiles.append(tile)
  (OUT/f'STAR{n}.BIN').write_bytes(blob);cv2.imwrite(str(REVIEW/f'star{n}-frames.png'),cv2.cvtColor(np.concatenate(tiles,axis=1),cv2.COLOR_RGB2BGR))
  sequences.append({'asset':f'STAR{n}.BIN','start_seconds':start,'period_seconds':period,'frames':10,'frame_seconds':.2,'registration':'HD5x center samples','bytes':len(blob)})
 cap.release();(REVIEW/'meteors.json').write_text(json.dumps(sequences,indent=2)+'\n')
 # Registration is verified independently against original game pixels, with clouds absent.
 match=float(np.mean(bg==original));assert match>.97,('Incorrect native registration',match)
 report['background_exact_palette_match']=match;report['motion']=motion;report['mask_corrected_pixels']=len(changes)
 # Keep the canonical tracking file aligned with the actual production assets.
 canonical={'video':'https://www.youtube.com/watch?v=ikaqus5_QIg','intervals_seconds':[[0,180],[1020,1200]],'native_transform':report['registration'],'speed_pixels_per_second':speed,'spacing_pixels':report['period_native'],'cloud_crop':report['crop'],'source_cloud':report['method'],'hd_report':'hd-recovery.json'}
 (REVIEW/'tracking.json').write_text(json.dumps(canonical,indent=2)+'\n')
 print('HD original-background match',match,'motion',motion,flush=True)
