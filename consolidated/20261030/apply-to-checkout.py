#!/usr/bin/env python3
"""Check pinned base/preimages; optionally apply the series on a new branch."""
from pathlib import Path
import argparse,hashlib,json,subprocess,sys
p=Path(__file__).resolve().parent
arg=argparse.ArgumentParser(description=__doc__)
arg.add_argument('checkout',type=Path)
arg.add_argument('--apply',action='store_true',help='Create the branch and git am after all checks pass')
arg.add_argument('--branch',default='integration/usb4-storage-display')
a=arg.parse_args();r=a.checkout.resolve();base='f7734f4c91c0f47d9e762786968057bec99a0788'
def git(*cmd):return subprocess.check_output(['git','-C',str(r),*cmd],text=True).strip()
if git('rev-parse','HEAD')!=base:sys.exit('Stop: checkout HEAD must be the pinned UbuntuAsahi base '+base)
if git('status','--porcelain'):sys.exit('Stop: checkout has local changes or untracked files; use a separate clean worktree.')
manifest=json.loads((p/'preimage-manifest.json').read_text())
for name,expected in manifest.items():
 f=r/name
 if expected is None:
  if f.exists():sys.exit('Stop: expected new path already exists: '+name)
 else:
  if not f.is_file():sys.exit('Stop: missing base path: '+name)
  b=f.read_bytes();actual=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
  if actual!=expected:sys.exit('Stop: base content differs: '+name)
files=[p/'patches'/x for x in (p/'series').read_text().splitlines() if x and not x.startswith('#')]
expected=json.loads((p/'patch-sha256.json').read_text())
for f in files:
 if hashlib.sha256(f.read_bytes()).hexdigest()!=expected[f.name]:sys.exit('Stop: patch checksum differs: '+f.name)
print('Base and all',len(manifest),'preimages verified;',len(files),'patches verified.')
if not a.apply:
 print('Check only. Use --apply to create a local branch; nothing is installed or published.')
 sys.exit(0)
subprocess.run(['git','-C',str(r),'switch','-c',a.branch],check=True)
subprocess.run(['git','-C',str(r),'am',*map(str,files)],check=True)
for name, digest in json.loads((p/'postimage-sha256.json').read_text()).items():
 if hashlib.sha256((r/name).read_bytes()).hexdigest()!=digest:sys.exit('Stop: applied content differs: '+name)
print('Applied and final contents verified on local branch',a.branch,'. No kernel installed, no push performed.')
