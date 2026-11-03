#!/usr/bin/env python3
"""Write verified foreground mattes; HD evidence is collected by finish_hd_assets."""
import json
from pathlib import Path
import cv2,numpy as np
ROOT=Path(__file__).resolve().parents[1]
def write_outputs(contour,report):
    dst=ROOT/'assets'
    (dst/'mountain-contour.json').write_text(json.dumps({'source':'ORIGINAL.EGA + observed video occlusion','method':report['method'],'y_by_x':contour.tolist()},indent=2)+'\n')
    (dst/'mountain-occlusion-evidence.json').write_text(json.dumps(report,indent=2)+'\n')
    sky=np.indices((200,320))[0]<contour[None,:]
    (dst/'SKY.MSK').write_bytes(np.packbits(sky,axis=1).tobytes())
    b=np.frombuffer((dst/'ORIGINAL.EGA').read_bytes(),np.uint8).reshape(4,200,40)
    original=sum(np.unpackbits(b[k],axis=1)*(1<<k) for k in range(4))
    palette=np.array(json.loads((dst/'palette.json').read_text())['rgb'],np.uint8)
    rgb=palette[original]
    cv2.imwrite(str(dst/'island-foreground.png'),cv2.cvtColor(np.dstack([rgb,(~sky).astype('uint8')*255]),cv2.COLOR_RGBA2BGRA))
    review=rgb.copy();review[sky]=[255,0,255]
    cv2.imwrite(str(ROOT/'research/clouds/mountain-matte.png'),cv2.cvtColor(review,cv2.COLOR_RGB2BGR))
    overlay=rgb.copy()
    for pixel in report['corrected_pixels']:overlay[pixel['y'],pixel['x']]=[255,0,0]
    cv2.imwrite(str(ROOT/'research/clouds/mask-corrections.png'),cv2.resize(cv2.cvtColor(overlay,cv2.COLOR_RGB2BGR),(960,600),interpolation=cv2.INTER_NEAREST))
    print('Corrected',len(report['corrected_pixels']),'edge pixels; video supports',len(report['stationary_terrain_pixels']),'terrain pixels')
if __name__=='__main__':
    raise SystemExit('Run recover_cloud_hd.py with registered1080p references to rebuild the mask.')
