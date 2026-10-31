#!/usr/bin/env python3
"""Publish compatible successful builds for installer discovery; never install them."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

REPO = 'frogro/m1-asahi-usb4-pcie'
BASE = 'f7734f4c91c0f47d9e762786968057bec99a0788'


def require(value, message):
    if not value:
        raise RuntimeError(message)


def gh(*args):
    return subprocess.check_output(['gh', *map(str, args)], text=True)


def api(path):
    return json.loads(gh('api', 'repos/' + REPO + '/' + path))


def build_manifest(run, release, directory):
    require(run.get('status') == 'completed' and run.get('conclusion') == 'success'
            and run.get('head_branch') == 'main' and run.get('event') == 'workflow_dispatch'
            and run.get('path') == '.github/workflows/consolidated-kernel.yml'
            and run.get('head_repository', {}).get('full_name') == REPO,
            'Not a successful trusted main-branch kernel build')
    require(release['tag_name'] == f"kernel-build-{run['id']}-{run['run_attempt']}", 'Wrong release identity')
    directory = Path(directory)
    require((directory/'RESULT.txt').read_text().strip() ==
            'Build and module checks passed. Not installed. Hardware validation pending.', 'Build checks did not pass')
    comparison = json.loads((directory/'config-comparison.json').read_text())
    require(comparison.get('result') == 'passed' and not comparison.get('unexpected_changes'), 'Configuration changed unexpectedly')
    version = (directory/'kernel-release.txt').read_text().strip()
    require(re.fullmatch(r'7\.2\.12-usb4sd4-egpu[0-9]+', version), 'Not the compatible complete eGPU profile')
    require('Commit: ' + run['head_sha'] in (directory/'RUN.txt').read_text(), 'Artifact/source mismatch')
    name = 'linux-' + version + '-arm64.tar.zst'
    archive = directory/name
    require(archive.is_file(), 'Missing complete kernel archive (split files unsupported)')
    with archive.open('rb') as f:
        checksum = hashlib.file_digest(f, 'sha256').hexdigest()
    sums = dict((line.split()[1].removeprefix('./'), line.split()[0])
                for line in (directory/'SHA256SUMS').read_text().splitlines() if len(line.split()) == 2)
    for file in ('RESULT.txt', 'config-comparison.json', 'kernel-release.txt', 'RUN.txt', name):
        require(sums.get(file) == hashlib.sha256((directory/file).read_bytes()).hexdigest(), 'Checksum mismatch: ' + file)
    assets = [a for a in release['assets'] if a['name'] == name]
    require(len(assets) == 1 and assets[0].get('digest') == 'sha256:' + checksum
            and assets[0]['size'] == archive.stat().st_size, 'GitHub asset differs from archive')
    # Verify actual payload without extracting any paths or executing build artifacts.
    listing = subprocess.check_output(['tar','--zstd','-tf',archive], text=True).splitlines()
    names = {n.removeprefix('./') for n in listing}
    require(not any(n.startswith('/') or '..' in Path(n).parts for n in names), 'Unsafe archive paths')
    needed = {f'boot/Image-{version}', f'boot/config-{version}',
              f'boot/dtbs/{version}/apple/t8103-j274.dtb',
              f'lib/modules/{version}/modules.dep', 'usr/lib/firmware/apple/avd-fw-v2-t0.bin'}
    require(needed <= names, 'Incomplete kernel/module/DTB/firmware payload: ' + str(needed-names))
    require(any(n.startswith(f'lib/modules/{version}/') and '/amdgpu.ko' in n for n in names), 'AMDGPU missing')
    return dict(schema=1, installer_contract='j274-egpu-v1', status='build-verified',
                hardware_validation='not-certified-by-build', architecture='arm64', machine='apple,j274',
                profile='egpu', release=version, kernel_base=BASE, build_commit=run['head_sha'],
                run_id=run['id'], run_attempt=run['run_attempt'],
                archive=dict(name=name, sha256=checksum, size=archive.stat().st_size))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', type=int, required=True)
    p.add_argument('--publish', action='store_true', help='Upload manifest and publish the verified build and mark the newest compatible build Latest')
    a = p.parse_args()
    run = api(f'actions/runs/{a.run}')
    require(run.get('status') == 'completed' and run.get('conclusion') == 'success', 'Build not finished successfully')
    tag = f"kernel-build-{a.run}-{run['run_attempt']}"
    release = api('releases/tags/' + tag)
    source = api('contents/build/full-kernel.sh?ref=' + run['head_sha'])
    script = base64.b64decode(source['content']).decode()
    require(re.search(r'^base=' + BASE + r'$', script, re.M), 'Kernel base requires renewed installer validation')
    # Only these successful-build files are needed; no source code from the triggering run is executed.
    with tempfile.TemporaryDirectory(prefix='asahi-publish-') as td:
        directory = Path(td)
        for pattern in ('RESULT.txt','config-comparison.json','kernel-release.txt','RUN.txt','SHA256SUMS','linux-*-arm64.tar.zst'):
            gh('release','download',tag,'--repo',REPO,'--pattern',pattern,'--dir',td)
        manifest = build_manifest(run, release, directory)
        target = directory/'installer-manifest.json'
        target.write_text(json.dumps(manifest, indent=2)+'\n')
        print(target.read_text())
        if a.publish:
            old = [asset for asset in release['assets'] if asset['name'] == target.name]
            if old:
                gh('release','download',tag,'--repo',REPO,'--pattern',target.name,'--dir',td+'/existing')
                require(json.loads((directory/'existing'/target.name).read_text()) == manifest,
                        'Existing installer manifest differs; refusing replacement')
            else:
                gh('release','upload',tag,target,'--repo',REPO)
            releases = []
            for page in range(1, 101):
                batch = api(f'releases?per_page=100&page={page}')
                releases.extend(batch)
                if len(batch) < 100:
                    break
            else:
                raise RuntimeError('Release listing incomplete; refusing to change Latest')
            identities = [tuple(map(int, r['tag_name'].split('-')[-2:]))
                          for r in releases
                          if not r.get('draft') and re.fullmatch(r'kernel-build-[0-9]+-[0-9]+',r.get('tag_name',''))
                          and any(x['name']=='installer-manifest.json' for x in r.get('assets',[]))]
            newest = (manifest['run_id'], manifest['run_attempt']) >= max(identities, default=(0,0))
            gh('release','edit',tag,'--repo',REPO,'--draft=false','--prerelease=false',
               '--latest='+str(newest).lower(),
               '--title',manifest['release']+' — build verified; hardware tests pending')
            print('Published compatible installer build:',tag)
        else:
            print('Validated only. No release changed.')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError, OSError, subprocess.CalledProcessError) as e:
        print('STOP:', e, file=sys.stderr)
        sys.exit(1)
