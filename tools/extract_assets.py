#!/usr/bin/env python3
"""Extract room 10 and its fire objects from the user's Monkey Island EGA copy.

No game execution or disk writes. Standard-library-only SCUMM v4 EGA decoder.
Format reference: ScummVM engines/scumm/gfx.cpp drawStripEGA and object.cpp
ScummEngine_v4::resetRoomObject. Output contains the user's original game art.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import zlib

PALETTE = [(0,0,0),(0,0,170),(0,170,0),(0,170,170),(170,0,0),(170,0,170),
           (170,85,0),(170,170,170),(85,85,85),(85,85,255),(85,255,85),
           (85,255,255),(255,85,85),(255,85,255),(255,255,85),(255,255,255)]
def u16(d,o): return struct.unpack_from('<H',d,o)[0]
def u32(d,o): return struct.unpack_from('<I',d,o)[0]
def decode(bm,w,h):
    """SCUMM EGA stripes: columns top-to-bottom, eight columns per strip."""
    out=bytearray(w*h)
    for strip in range(w//8):
        p=u16(bm,2+strip*2); n=0
        while n<h*8:
            c=bm[p]; p+=1
            if c&128:
                run=c&63
                if c&64:
                    color=bm[p]; p+=1
                    if not run: run=bm[p]; p+=1
                    values=(color>>4,color&15)
                    for z in range(run):
                        x,y=divmod(n,h); out[y*w+strip*8+x]=values[z&1]; n+=1
                else:
                    if not run: run=bm[p]; p+=1
                    for _ in range(run):
                        x,y=divmod(n,h)
                        assert strip*8+x>0, 'Invalid previous-column reference'
                        out[y*w+strip*8+x]=out[y*w+strip*8+x-1]; n+=1
            else:
                run=c>>4
                if not run: run=bm[p]; p+=1
                for _ in range(run):
                    x,y=divmod(n,h); out[y*w+strip*8+x]=c&15; n+=1
            assert n<=h*8, 'Run crosses strip boundary'
    return out

def png(path,raw,w,h):
    def chunk(tag,data):
        return struct.pack('>I',len(data))+tag+data+struct.pack('>I',zlib.crc32(tag+data)&0xffffffff)
    scan=b''.join(b'\0'+bytes(raw[y*w:(y+1)*w]) for y in range(h))
    path.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',w,h,8,3,0,0,0))+
                     chunk(b'PLTE',bytes(v for c in PALETTE for v in c))+chunk(b'IDAT',zlib.compress(scan))+chunk(b'IEND',b''))

def planar(raw):
    return bytes(sum(((raw[y*320+x*8+b]>>p)&1)<<(7-b) for b in range(8))
                 for p in range(4) for y in range(200) for x in range(40))

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    source_args=ap.add_mutually_exclusive_group(required=True)
    source_args.add_argument('--image')
    source_args.add_argument('--game-dir',type=Path)
    ap.add_argument('--offset',type=int,default=0)
    ap.add_argument('--mtype',default='mtype')
    ap.add_argument('--game-path',default='::/GAMES/ADV/MONKEY/CGA/')
    ap.add_argument('--output',type=Path,default=Path(__file__).resolve().parents[1]/'assets')
    args=ap.parse_args(); dst=args.output; dst.mkdir(parents=True,exist_ok=True)
    source=args.game_path.rstrip('/')+'/'
    def read(name):
        if args.game_dir:return (args.game_dir/name).read_bytes()
        return subprocess.check_output([args.mtype,'-i',args.image+'@@'+str(args.offset),source+name])
    index=read('000.LFL')
    if hashlib.md5(index).hexdigest()!='1d05cd189e4908f79b57e78a4402f292':
        raise SystemExit('Unsupported game edition: expected English DOS EGA 000.LFL')
    packed=read('DISK01.LEC'); d=bytes(x^0x69 for x in packed)
    assert d[4:6]==b'LE' and d[10:12]==b'FO'
    rooms={d[13+i*5]:u32(d,14+i*5) for i in range(d[12])}
    start=rooms[10]+8; end=start+u32(d,start); assert d[start+4:start+6]==b'RO'
    p=start+6; chunks={}; objects={}
    while p<end:
        size=u32(d,p); tag=d[p+4:p+6]; assert size>=6 and p+size<=end
        chunks[tag]=d[p:p+size]
        if tag==b'OI': objects[u16(d,p+6)]=d[p:p+size]
        p+=size
    w,h=u16(chunks[b'HD'],6),u16(chunks[b'HD'],8)
    assert (w,h)==(640,200)
    room=decode(chunks[b'BM'][6:],w,h)
    raw=bytes(room[y*w+x] for y in range(200) for x in range(320))
    data=planar(raw)
    for name in ('ORIGINAL.EGA','ISLAND.EGA'): (dst/name).write_bytes(data)
    png(dst/'island.png',raw,320,200)
    frames=[decode(objects[n][8:],16,32) for n in range(117,122)]
    (dst/'FIRE.BIN').write_bytes(struct.pack('<HHH',16,32,len(frames))+b''.join(frames))
    for n,f in enumerate(frames): png(dst/f'fire-{n}.png',f,16,32)
    manifest={'source_image':args.image,'partition_offset':args.offset,'game_path':source,
              'index_md5':hashlib.md5(index).hexdigest(),'disk01_sha256':hashlib.sha256(packed).hexdigest(),
              'room':10,'room_size':[w,h],'crop':[0,0,320,200],
              'pixel_edits':False,'native_fire_objects':[117,118,119,120,121],
              'native_fire_rectangle':[136,0,16,32],
              'palette_rgb':PALETTE,'plane_layout':'plane0..3, 8000 bytes each, MSB is left pixel',
              'island_planar_sha256':hashlib.sha256(data).hexdigest(),
              'note':'Base has original stars, no clouds or moon. Fire frames are opaque replacements at136,0.'}
    (dst/'provenance.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('Extracted original room10 left320x200 and five native fire frames into',dst)
if __name__=='__main__': main()
