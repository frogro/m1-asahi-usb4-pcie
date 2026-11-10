#!/usr/bin/env python3
"""Apply the hash-pinned M1 integration to exactly the reviewed Asahi release."""
import argparse,hashlib,json,subprocess
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);a=p.parse_args()
here=Path(__file__).resolve().parent;m=json.loads((here/'manifest.json').read_text())
g=lambda *args: subprocess.check_output(['git','-C',str(a.source),*args],text=True).strip()
if g('rev-parse','HEAD')!=m['base_commit'] or g('status','--porcelain'):raise SystemExit('Expected clean pinned Asahi checkout')
h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for n,v in m['preimages'].items():
 f=a.source/n
 if (h(f) if f.exists() else None)!=v:raise SystemExit('Source preimage mismatch: '+n)
patch=here/'0001-m1-usb4-integrated.patch'
if h(patch)!=m['patch_sha256']:raise SystemExit('Patch hash mismatch')
subprocess.run(['git','-C',str(a.source),'apply','--check',str(patch)],check=True)
subprocess.run(['git','-C',str(a.source),'apply',str(patch)],check=True)
for n,v in m['postimages'].items():
 if h(a.source/n)!=v:raise SystemExit('Source postimage mismatch: '+n)
subprocess.run(['git','-C',str(a.source),'add','--',*m['postimages']],check=True)
subprocess.run(['git','-C',str(a.source),'commit','-m','Integrate reviewed M1 USB4, PCIe, eGPU and display port on Asahi 7.3.3'],check=True)
print('Validated',len(m['postimages']),'source postimages; hardware testing remains required')
