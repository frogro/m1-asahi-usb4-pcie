#!/usr/bin/env python3
"""Append the experimental eGPU series after the verified 29-patch series."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

here = Path(__file__).resolve().parent
tree = Path(sys.argv[1]).resolve()

def verify(manifest):
    for name, expected in json.loads((here / manifest).read_text()).items():
        path = tree / name
        actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
        if actual != expected:
            raise SystemExit('Source hash mismatch: ' + name)

if subprocess.check_output(['git', '-C', str(tree), 'status', '--porcelain'], text=True):
    raise SystemExit('Expected a clean checkout after the 29-patch application')
verify('preimage-sha256.json')
names = (here / 'series').read_text().splitlines()
hashes = json.loads((here / 'patch-sha256.json').read_text())
patches = [here / 'patches' / name for name in names]
for patch in patches:
    if hashlib.sha256(patch.read_bytes()).hexdigest() != hashes[patch.name]:
        raise SystemExit('Patch hash mismatch: ' + patch.name)
subprocess.run(['git', '-C', str(tree), 'am', *map(str, patches)], check=True)
verify('postimage-sha256.json')
print('Verified 13 eGPU patches and all 25 resulting source files. No installation.')
