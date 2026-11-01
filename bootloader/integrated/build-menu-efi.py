#!/usr/bin/env python3
"""Build this installation's EFI GRUB menu loader; never install it."""
import argparse
import hashlib
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--modules-dir', required=True, type=Path)
parser.add_argument('--output', required=True, type=Path)
args = parser.parse_args()
here = Path(__file__).resolve().parent
if args.output.exists():
    parser.error('output already exists; choose a new file')
if args.modules_dir.name != 'arm64-efi':
    parser.error('module directory must be an arm64-efi directory')
modules = ('normal minicmd part_gpt ext2 fat search search_fs_uuid ls cat echo '
           'test linux reboot sleep configfile loadenv gzio efi_gop').split()
for name in modules:
    if not (args.modules_dir / (name + '.mod')).is_file():
        parser.error('missing ARM64 module: ' + name)
for name in ['grub-bootstrap.cfg', 'grub.cfg', 'independent-esp-grub.cfg']:
    subprocess.run(['grub-script-check', str(here / name)], check=True)
subprocess.run([
    'grub-mkimage', '-O', 'arm64-efi', '-d', str(args.modules_dir),
    '-p', '/EFI/Asahi', '-c', str(here / 'grub-bootstrap.cfg'),
    '-o', str(args.output), *modules,
], check=True)
print(hashlib.sha256(args.output.read_bytes()).hexdigest(), args.output)
