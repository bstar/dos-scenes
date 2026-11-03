#!/usr/bin/env python3
"""Fetch the pinned upstream Linux SDK for CI without rebuilding the compiler."""
import argparse,hashlib,shutil,tempfile,urllib.request,zipfile
from pathlib import Path,PurePosixPath
ROOT=Path(__file__).resolve().parents[1]
URL='https://github.com/open-watcom/open-watcom-v2/releases/download/2026-11-01-Build/open-watcom-2_0-c-linux-x64'
SHA256='9d9d823c2ee040a38484ad74ad4a594e904672184e4e8fff84b3bac7090c9f6c'
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=ROOT/'build/toolchains/watcom');p.add_argument('--archive',type=Path,help='Use a local copy of the same checksum-verified SDK');a=p.parse_args()
a.output=a.output.resolve();a.output.parent.mkdir(parents=True,exist_ok=True)
if a.output.exists():p.error('Output already exists; choose a fresh SDK directory')
with tempfile.TemporaryDirectory(prefix='watcom-',dir=a.output.parent) as temporary:
 stage=Path(temporary);archive=a.archive or stage/'sdk.zip'
 if not a.archive:
  print('Downloading pinned Open Watcom 2026-11-01 SDK',flush=True)
  with urllib.request.urlopen(URL,timeout=120) as src,archive.open('wb') as dst:shutil.copyfileobj(src,dst)
 with archive.open('rb') as src:digest=hashlib.file_digest(src,'sha256').hexdigest()
 if digest!=SHA256:p.error('SDK SHA-256 does not match pinned upstream asset')
 sdk=stage/'sdk';sdk.mkdir()
 # The upstream self-extracting archive is also a ZIP. Extract the SDK files;
 # do not execute its installer or copy unrelated targets into the build.
 with zipfile.ZipFile(archive) as z:
  for item in z.infolist():
   parts=PurePosixPath(item.filename).parts
   if not parts or parts[0] not in ('binl64','h','lib286'):continue
   if PurePosixPath(item.filename).is_absolute() or '..' in parts:p.error('Invalid SDK archive path')
   dest=sdk.joinpath(*parts)
   if item.is_dir():dest.mkdir(parents=True,exist_ok=True);continue
   dest.parent.mkdir(parents=True,exist_ok=True)
   with z.open(item) as src,dest.open('wb') as dst:shutil.copyfileobj(src,dst)
   if parts[0]=='binl64':dest.chmod(0o755)
 for name in ('binl64/wcl','binl64/wcc','binl64/wlink','binl64/wasm','h/dos.h','lib286/dos/clibl.lib'):
  if not (sdk/name).is_file():p.error('SDK is incomplete: '+name)
 (sdk/'SOURCE.TXT').write_text(f'{URL}\nsha256:{SHA256}\n')
 sdk.rename(a.output)
print('Verified SDK:',a.output)
