#!/usr/bin/env python3
"""Apply verified Ubuntu display stack and queued audio unlock; no deployment."""
import argparse, hashlib, json, subprocess
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);a=p.parse_args()
here=Path(__file__).resolve().parent
series=json.loads((here/'series.json').read_text())['patches']
patches=[]
for item in series:
 patch=here/item['file']
 if hashlib.sha256(patch.read_bytes()).hexdigest()!=item['sha256']:raise SystemExit('hash mismatch: '+str(patch))
 patches.append(patch)
patches.append(here.parent/'next-build/audio-open-lock/0001-drm-apple-release-audio-lock-on-DMA-error.patch')
# Check the complete sequence in a temporary index before changing any source.
import tempfile,os
with tempfile.TemporaryDirectory() as tmp:
 env=os.environ.copy();env['GIT_INDEX_FILE']=str(Path(tmp)/'index')
 subprocess.run(['git','-C',str(a.source),'read-tree','HEAD'],env=env,check=True)
 for patch in patches:
  subprocess.run(['git','-C',str(a.source),'apply','--cached',str(patch)],env=env,check=True)
for patch in patches:subprocess.run(['git','-C',str(a.source),'apply',str(patch)],check=True)
subprocess.run(['git','-C',str(a.source),'add','-u'],check=True)
# Include only newly added files named by the verified patches.
for patch in patches:
 for line in patch.read_text().splitlines():
  if line.startswith('+++ b/'):
   subprocess.run(['git','-C',str(a.source),'add','--',line[6:]],check=True)
subprocess.run(['git','-C',str(a.source),'commit','-m','Integrate opt-in automatic display routing and audio error unlock'],check=True)
