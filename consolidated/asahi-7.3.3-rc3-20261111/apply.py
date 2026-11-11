#!/usr/bin/env python3
"""Apply the pinned rc3 series with per-stage and final tree verification."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('kernel',type=Path)
p.add_argument('--before-dir',type=Path,required=True)
a=p.parse_args();a.kernel=a.kernel.resolve();a.before_dir=a.before_dir.resolve()
recipe=Path(__file__).resolve().parent;repo=recipe.parents[1]
m=json.loads((recipe/'manifest.json').read_text())
def git(*args):
 return subprocess.check_output(['git','-C',str(a.kernel),*args],text=True).strip()
def digest(path):
 return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
def images(expected):
 for path,want in expected.items():
  got=digest(a.kernel/path)
  if got!=want:raise SystemExit(f'Hash mismatch: {path}: {got} != {want}')
if git('status','--porcelain','--untracked-files=normal'):
 raise SystemExit('Refusing a dirty kernel worktree')
if git('rev-parse','HEAD')!=m['base_commit']:
 raise SystemExit('Wrong Asahi base commit')
for entry in m['series']:
 patch=repo/entry['patch']
 if digest(patch)!=entry['sha256']:raise SystemExit('Patch hash mismatch: '+str(patch))
 images(entry['preimages'])
 if entry.get('stage')=='rc2':
  for path in entry['preimages']:
   target=a.before_dir/path;target.parent.mkdir(parents=True,exist_ok=True)
   shutil.copyfile(a.kernel/path,target)
 git('apply','--check',str(patch));git('apply',str(patch));git('diff','--check')
 images(entry['postimages'])
 git('add','--',*entry['postimages'])
 git('commit','-qm',entry['name'])
 if entry.get('stage')=='rc2' and git('rev-parse','HEAD^{tree}')!=m['rc2_tree']:
  raise SystemExit('Rebased rc2 tree mismatch')
 print('Verified:',entry['name'],flush=True)
if git('rev-parse','HEAD^{tree}')!=m['final_tree']:
 raise SystemExit('Final source tree mismatch')
print('Verified final rc3 tree:',m['final_tree'])
