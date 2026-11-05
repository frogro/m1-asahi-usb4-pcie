#!/usr/bin/env python3
"""Prepare a fresh Ubuntu Mutter 50.1 source package; does not install packages."""
import argparse,hashlib,json,subprocess
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);a=p.parse_args();src=a.source.resolve();here=Path(__file__).resolve().parent
changelog=src/'debian/changelog'
if not changelog.read_text().startswith('mutter (50.1-0ubuntu2.5) '):raise SystemExit('Expected pristine, dpkg-source extracted Ubuntu 50.1-0ubuntu2.5')
for item in json.loads((here/'manifest.json').read_text())['patches']:
 patch=here/item['file']
 if hashlib.sha256(patch.read_bytes()).hexdigest()!=item['sha256']:raise SystemExit('Patch hash mismatch')
 subprocess.run(['patch','--batch','--fuzz=0','-p1','--dry-run','-i',str(patch)],cwd=src,check=True)
 subprocess.run(['patch','--batch','--fuzz=0','-p1','-i',str(patch)],cwd=src,check=True)
changelog.write_text('''mutter (50.1-0ubuntu2.5+asahi.hotplug3) resolute; urgency=medium

  * Reconfigure monitors after runtime GPU addition.
  * Backport upstream MR5207 per-view software cursor handling.
  * Recover bad connector link status through an active atomic modeset.

 -- Local Ubuntu Asahi Development <local@localhost>  Thu, 05 Nov 2026 00:00:00 +0000

'''+changelog.read_text())
print('Prepared only. Build using dpkg-buildpackage in an isolated Ubuntu resolute environment; run the test groups documented in README.md.')
