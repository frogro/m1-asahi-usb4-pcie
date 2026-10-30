#!/usr/bin/env python3
from pathlib import Path
import hashlib
p=Path('artifacts')
limit=1900*1024*1024
for f in list(p.iterdir()):
 if f.is_file() and f.stat().st_size>=limit:
  with f.open('rb') as src:
   i=0
   while True:
    block=src.read(limit)
    if not block:break
    f.with_name(f.name+f'.part{i:03d}').write_bytes(block)
    i+=1
  f.unlink()
with (p/'SHA256SUMS').open('w') as out:
 for f in sorted(p.iterdir()):
  if f.is_file() and f.name!='SHA256SUMS':
   with f.open('rb') as src:digest=hashlib.file_digest(src,'sha256').hexdigest()
   out.write(f'{digest}  {f.name}\n')
