#!/usr/bin/env python3
"""Apply rc2 follow-ups to the exact rc1 integrated source tree."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('source', type=Path)
p.add_argument('--before-dir', required=True, type=Path)
a = p.parse_args()
here = Path(__file__).resolve().parent
m = json.loads((here / 'manifest.json').read_text())
def git(*args):
    return subprocess.check_output(['git', '-C', str(a.source), *args], text=True).strip()
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
if git('status', '--porcelain') or git('rev-parse', 'HEAD^{tree}') != m['integrated_tree']:
    raise SystemExit('Expected clean, hash-pinned rc1 integrated tree')
patch = here / '0001-amdgpu-accounting-and-offline-dm.patch'
if sha(patch) != m['patch_sha256']:
    raise SystemExit('Patch hash mismatch')
for name, expected in m['preimages'].items():
    f = a.source / name
    if sha(f) != expected:
        raise SystemExit('Preimage mismatch: ' + name)
    before = a.before_dir / name
    if before.exists():
        raise SystemExit('Refusing to overwrite before-image: ' + str(before))
    before.parent.mkdir(parents=True, exist_ok=True)
    before.write_bytes(f.read_bytes())
subprocess.run(['git', '-C', str(a.source), 'apply', '--check', str(patch)], check=True)
subprocess.run(['git', '-C', str(a.source), 'apply', str(patch)], check=True)
for name, expected in m['postimages'].items():
    if sha(a.source / name) != expected:
        raise SystemExit('Postimage mismatch: ' + name)
subprocess.run(['git', '-C', str(a.source), 'diff', '--check'], check=True)
subprocess.run(['git', '-C', str(a.source), 'add', '--', *m['postimages']], check=True)
subprocess.run(['git', '-C', str(a.source), 'commit', '-m',
                'Fix VM accounting symmetry and avoid offline display power requests'], check=True)
print('Validated rc2 follow-ups; hardware testing remains required')
