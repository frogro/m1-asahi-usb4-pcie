#!/usr/bin/env python3
"""Rebuild the USB4 child development source; never install or publish."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--jobs', type=int, default=4)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 32:
        parser.error('jobs must be between 1 and 32')
    here = Path(__file__).resolve().parent
    manifest = json.loads((here / 'manifest.json').read_text())
    for item in manifest['patches']:
        if hashlib.sha256((here / item['file']).read_bytes()).hexdigest() != item['sha256']:
            raise SystemExit('Patch hash mismatch: ' + item['file'])
    if hashlib.sha256((here / 'apple.config').read_bytes()).hexdigest() != manifest['config_sha256']:
        raise SystemExit('Config hash mismatch')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    work = output / 'source'
    env = os.environ.copy()
    env['SOURCE_DATE_EPOCH'] = subprocess.check_output(
        ['git', '-C', str(args.source), 'show', '-s', '--format=%ct', manifest['base_commit']], text=True).strip()
    env.pop('CROSS_COMPILE', None)
    def run(command, name, cwd=work):
        with (output / (name + '.log')).open('w') as log:
            subprocess.run(list(map(str, command)), cwd=cwd, env=env,
                           stdout=log, stderr=subprocess.STDOUT, check=True)
    run(['git', '-C', args.source.resolve(), 'worktree', 'add', '--detach', work,
         manifest['base_commit']], 'checkout', output)
    for index, item in enumerate(manifest['patches']):
        patch = (here / item['file']).resolve()
        run(['git', 'apply', '--check', patch], f'patch-{index}-check')
        run(['git', 'apply', patch], f'patch-{index}')
    for name, expected in manifest['source_identity'].items():
        if hashlib.sha256((work / name).read_bytes()).hexdigest() != expected:
            raise SystemExit('Reconstructed source mismatch: ' + name)
    for name in ['test-recovery-r5.py','test-port-retry.py','test-speed.py','test-handoff.py']:
        run(['python3', here.parent / 'usb3-recovery' / name, work, output / 'tests'], name)
    for name in ['test-router.py','test-write-guard.py','test-nested.py','test-child-events.py']:
        run(['python3', here / name, work, output / 'tests'], name)
    build = output / 'apple'
    build.mkdir()
    shutil.copy2(here / 'apple.config', build / '.config')
    make = ['make', f'O={build}', 'CROSS_COMPILE=aarch64-linux-gnu-']
    run(make + ['olddefconfig'], 'apple-config')
    run(make + [f'-j{args.jobs}'], 'apple-build')
    config = (build / '.config').read_text()
    for key in ['NVME_APPLE', 'NVME_PCI', 'USB_STORAGE', 'CMD_APPLE_ATC_M1', 'EFI_VARIABLE_NO_STORE']:
        if f'CONFIG_{key}=y\n' not in config:
            raise SystemExit('Missing feature: ' + key)
    result = {'version': manifest['version'], 'base_commit': manifest['base_commit'],
              'source_identity_verified': True, 'software_tests_passed': True,
              'uboot_sha256': hashlib.sha256((build / 'u-boot-nodtb.bin').read_bytes()).hexdigest(),
              'installed': False, 'hardware_test_of_this_rebuild': False,
              'full_googlebook_image_built': False}
    (output / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))

if __name__ == '__main__':
    main()
