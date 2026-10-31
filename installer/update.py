#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare an additional kernel on existing internal Ubuntu/Fedora Asahi.
Default: read-only plan. No disk formatting, user creation or distribution upgrade.
Internal Ubuntu boot validated; peripheral and Fedora validation remain incomplete.
"""
import argparse
import contextlib
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import install as core

STATE_ROOT = Path('/var/lib/asahi-kernel-update')
STATE = STATE_ROOT / core.RELEASE


def boot_storage(root, boot, free_boot):
    if free_boot >= 450*1024**2:
        return dict(boot_directory='/boot',boot_prefix='',boot_uuid=core.uuid_ok(boot['uuid']))
    # GRUB can read the already supported unencrypted internal root filesystem.
    # Keep every existing /boot artifact rather than deleting an older kernel.
    directory=STATE/'boot'
    subvolume=root['fsroot'].strip('/') if root['fstype']=='btrfs' else ''
    prefix='/'+'/'.join(v for v in (subvolume,str(directory).lstrip('/')) if v)
    return dict(boot_directory=str(directory),boot_prefix=prefix,boot_uuid=core.uuid_ok(root['uuid']))


def kernel_version(release):
    match=re.match(r'^(\d+)\.(\d+)(?:\.(\d+))?',release)
    core.require(match is not None, 'Cannot determine kernel version: '+release)
    return tuple(int(v or 0) for v in match.groups())


def installed_releases():
    values={platform.release()}
    values.update(p.name for p in Path('/lib/modules').iterdir() if p.is_dir())
    values.update(p.name.removeprefix('vmlinuz-') for p in Path('/boot').glob('vmlinuz-*'))
    values.update(p.name.removeprefix('Image-') for p in Path('/boot').glob('Image-*'))
    return sorted(values)


def newer_releases(releases):
    # Suffixes identify different patch/package variants, not a reliable ordering.
    return [r for r in releases if kernel_version(r)>kernel_version(core.RELEASE)]


def os_info():
    fields = {}
    for line in Path('/etc/os-release').read_text().splitlines():
        if '=' in line:
            key, val = line.split('=', 1)
            fields[key] = val.strip('"')
    return fields


def commands(os_id):
    core.require(os_id in ('ubuntu', 'fedora'), 'Only Ubuntu Asahi / Fedora Asahi supported')
    if os_id == 'fedora':
        return dict(check='grub2-script-check', rebuild=['grub2-mkconfig', '-o', '/boot/grub2/grub.cfg'],
                    reboot='grub2-reboot', edit='grub2-editenv', cfg='/boot/grub2/grub.cfg',
                    env='/boot/grub2/grubenv')
    return dict(check='grub-script-check', rebuild=['update-grub'], reboot='grub-reboot',
                edit='grub-editenv', cfg='/boot/grub/grub.cfg', env='/boot/grub/grubenv')


def context():
    info = os_info()
    cmd = commands(info.get('ID'))
    root = json.loads(core.output('findmnt', '--json', '--mountpoint', '/', '-o',
                                  'SOURCE,UUID,FSTYPE,FSROOT'))['filesystems'][0]
    boot = json.loads(core.output('findmnt', '--json', '--mountpoint', '/boot', '-o',
                                  'SOURCE,UUID,FSTYPE'))['filesystems'][0]
    esp = core.uuid_ok(core.output('findmnt', '-n', '-o', 'UUID', '--mountpoint', '/boot/efi'))
    core.require(root['source'].startswith('/dev/nvme') and root['fstype'] in ('ext4','btrfs'),
                 'This version requires a directly mounted internal NVMe ext4/btrfs root (no LUKS/LVM)')
    core.require(boot['fstype'] == 'ext4' and boot['uuid'] != root['uuid'],
                 'This version requires a separate ext4 /boot partition')
    source = root['source'].split('[')[0]
    parent = core.output('lsblk','-n','-o','PKNAME',source).strip()
    model = core.output('lsblk','-dn','-o','MODEL','/dev/'+Path(parent).name)
    return dict(os_id=info['ID'], os_name=info.get('PRETTY_NAME'), commands=cmd,
                root_uuid=core.uuid_ok(root['uuid']), system_boot_uuid=core.uuid_ok(boot['uuid']),
                internal_esp_uuid=esp, root_subvolume=root['fsroot'] if root['fstype']=='btrfs' else '/',
                root_fstype=root['fstype'], release=core.RELEASE, model=model, target='internal-update',
                **boot_storage(root,boot,shutil.disk_usage('/boot').free))


def preflight(m, space=True):
    core.require(os.geteuid() == 0, 'Use sudo for update preparation')
    core.require(platform.machine() == 'aarch64', 'Run on the target Mac')
    compat=Path('/proc/device-tree/compatible').read_bytes().split(b'\0')
    core.require(b'apple,j274' in compat and b'apple,t8103' in compat, 'J274 Mac mini M1 only')
    cmd=m['commands']
    required=['dracut','lsinitrd','modinfo','depmod','fdtget','zstd','tar','mount','umount',
              'systemd-inhibit',cmd['check'],cmd['rebuild'][0],cmd['reboot'],cmd['edit']]
    if m['os_id']=='fedora': required += ['restorecon','getenforce']
    core.require(all(shutil.which(c) for c in required), 'Missing update tools: '+', '.join(c for c in required if not shutil.which(c)))
    live=Path('/boot/efi/m1n1/boot.bin')
    core.require(live.is_file() and Path(cmd['cfg']).is_file(), 'Existing Asahi m1n1/GRUB setup missing')
    core.require(not list(live.parent.glob('*.armed')) and not (live.parent/'usb-test-armed').exists(), 'Another boot is armed')
    core.require(not core.pending_grub_entries(core.output(cmd['edit'],cmd['env'],'list')), 'Another one-time GRUB selection is pending')
    if space:
        if m['boot_directory']=='/boot':
            core.require(shutil.disk_usage('/boot').free >= 450*1024**2, 'At least 450 MiB free in /boot required')
        core.require(shutil.disk_usage('/').free >= 3*core.GIB, 'At least 3 GiB free in root required')
        core.require(shutil.disk_usage(live.parent).free >= 2*live.stat().st_size+2*1024**2,
                     'ESP needs room for a bundle backup and atomic staging')
    core.require('module.sig_enforce=1' not in Path('/proc/cmdline').read_text(),
                 'Enforced module signature policy requires a separately validated key enrollment')
    core.boot_options(m)
    core.grub_entry(m)


def plan():
    print('READ-ONLY: add a kernel; preserve users, /home, network settings and old kernels.')
    print('Selected build:',core.RELEASE,core.BUILD_COMMIT)
    releases=installed_releases()
    print('Installed/running releases:', ', '.join(releases))
    newer=newer_releases(releases)
    if newer: print('Newer upstream versions exist; --prepare requires explicit --allow-older:', ', '.join(newer))
    if core.RELEASE in releases: print('Exact release already present: no blind overwrite; inspect provenance and existing update state.')
    try:
        m=context()
        print(json.dumps(m,indent=2))
        print(core.grub_entry(m))
        print('Free /boot MiB:',shutil.disk_usage('/boot').free//1024**2)
    except (RuntimeError, OSError, subprocess.CalledProcessError) as e:
        print('Current host is not eligible:',e)
    print('No disk is formatted. No apt/dnf distribution upgrade. No automatic reboot.')


def relative_path(value):
    path=Path(value)
    core.require(not path.is_absolute() and '..' not in path.parts and path.parts,
                 'Expected a relative installation path: '+str(value))
    return path


def save_and_write(relative, content, changed, mode=0o644, root=Path('/')):
    relative=relative_path(relative).as_posix()
    dest=root/relative
    core.require(not dest.is_symlink(), 'Refusing to replace a symlink: '+str(dest))
    backup=STATE/'previous'/relative
    existed=dest.exists()
    if existed:
        backup.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(dest,backup)
    changed.append(dict(path=relative,existed=existed))
    core.atomic(dest,content,mode)


def restore_changed(changed, root=Path('/')):
    for record in reversed(changed):
        relative=relative_path(record['path'])
        dest=root/relative
        if record['existed']:
            shutil.copy2(STATE/'previous'/relative,dest)
        else:
            dest.unlink(missing_ok=True)


def verify_preserved_boot_selection(before, after, entry):
    # Adding a kernel must not renumber existing explicit menu entries or alter
    # the generated default selection. BLS entries remain managed by Fedora.
    menus=lambda text: re.findall(r'^\s*(?:menuentry|submenu)\s+.*$',text,re.M)
    old=menus(before)
    new=menus(after)
    core.require(new==old+menus(entry), 'Existing GRUB menu order changed; refusing activation')
    defaults=lambda text: re.findall(r'^\s*set\s+default=.*$',text,re.M)
    core.require(defaults(before)==defaults(after), 'GRUB default changed; refusing activation')


def dracut_setup(release, backup_path):
    core.release_name(release)
    relative_path(backup_path)
    setup='''#!/bin/bash
check() { [ "$kernel" = '@RELEASE@' ] || return 1; return 0; }
depends() { echo fs-lib; }
installkernel() { instmods nvme_apple vfat; }
install() {
    inst_multiple blkid mount umount modprobe sha256sum cut cp mv rm mkdir sync touch
    inst_simple /@BACKUP@
    inst_hook initqueue/settled 05 "$moddir/restore.sh"
    inst_hook pre-mount 05 "$moddir/restore.sh"
}
'''
    return setup.replace('@RELEASE@',release).replace('@BACKUP@',backup_path)


def prepare(allow_older=False):
    m=context();preflight(m)
    releases=installed_releases()
    core.require(core.RELEASE not in releases, 'Exact release already installed or running; refusing overwrite')
    newer=newer_releases(releases)
    core.require(not newer or allow_older, 'Newer kernel(s) installed: '+', '.join(newer)+'. Use --allow-older only for an additional test kernel; defaults stay unchanged.')
    core.require(not STATE.exists(), 'This release already has update state; inspect it before retrying')
    boot=Path(m['boot_directory'])
    core.require(not Path('/lib/modules',core.RELEASE).exists(), 'Matching module directory already exists')
    for prefix in ('Image-','vmlinuz-','initrd.img-','config-','System.map-'):
        core.require(not (boot/(prefix+core.RELEASE)).exists(), 'Matching boot file already exists: '+prefix+core.RELEASE)
    core.require(not (boot/'dtbs'/core.RELEASE).exists(), 'Matching DTB directory already exists')
    module = 'asahi-kernel-update-' + core.release_name(core.RELEASE)
    hook_dir = 'usr/lib/dracut/modules.d/92' + module
    backup_path = 'usr/lib/asahi-kernel-update/' + core.RELEASE + '/boot-original.bin'
    core.require(not Path('/'+hook_dir).exists(), 'This version already has an update hook')
    m.update(boot_manager_schema=2, entry_id='asahi-update-'+m['root_uuid']+'-'+core.RELEASE)
    print('Prepare additional kernel:',core.RELEASE,'on',m['os_name'])
    print('Keep all existing users, settings and kernels. Boot default remains unchanged.')
    core.require(input('Type PREPARE to continue: ') == 'PREPARE','Cancelled')
    STATE.mkdir(parents=True,mode=0o700)
    m.update(status='preparing',selected_build=core.SELECTED_BUILD,build_commit=core.BUILD_COMMIT,kernel_base=core.KERNEL_BASE,
             kernel_sha256=core.KERNEL_SHA,changed=[])
    core.json_write(STATE/'manifest.json',m)
    # Preserve account databases as hashes only, never store their contents in the manifest.
    identity_files=['/etc/passwd','/etc/shadow','/etc/group','/etc/gshadow']
    before={p:core.digest(p) for p in identity_files}
    inhibitor=subprocess.Popen(['systemd-inhibit','--what=sleep:shutdown','--mode=block',
                               '--why=Preparing additional Asahi kernel','sleep','infinity'])
    grub=Path(m['commands']['cfg']);grub_before=grub.read_bytes()
    core.atomic(STATE/'grub.cfg.before',grub_before)
    try:
        core.require(inhibitor.poll() is None, 'Could not inhibit sleep during preparation')
        archive=core.download(core.KERNEL_URL,core.KERNEL_SHA,STATE/'kernel.tar.zst')
        with tempfile.TemporaryDirectory(prefix='stage-',dir=STATE) as td:
            stage=Path(td)
            core.run('tar','--zstd','-xf',archive,'-C',stage,'--no-same-owner')
            original=Path('/boot/efi/m1n1/boot.bin').read_bytes()
            candidate=core.replace_dtb(original,(stage/'boot/dtbs'/core.RELEASE/'apple/t8103-j274.dtb').read_bytes())
            m.update(original_sha=hashlib.sha256(original).hexdigest(),candidate_sha=hashlib.sha256(candidate).hexdigest())
            core.atomic(STATE/'boot-original.bin',original)
            core.atomic(STATE/'boot-candidate.bin',candidate)
            # These new version-specific trees cannot replace an existing kernel.
            shutil.copytree(stage/'lib/modules'/core.RELEASE,Path('/lib/modules')/core.RELEASE,symlinks=True)
            shutil.copytree(stage/'boot/dtbs'/core.RELEASE,boot/'dtbs'/core.RELEASE,symlinks=True)
            for prefix in ('Image-','config-','System.map-'):
                save_and_write(str((boot/(prefix+core.RELEASE)).relative_to('/')),(stage/'boot'/ (prefix+core.RELEASE)).read_bytes(),m['changed'])
            for file in (stage/'usr').rglob('*'):
                if not file.is_file():continue
                relative=file.relative_to(stage).as_posix()
                allowed=('usr/lib/firmware/apple/avd-fw-', 'usr/share/doc/asahi-avd-firmware-local/',
                         'usr/share/alsa/ucm2/apple_dcp/', 'usr/share/alsa/ucm2/conf.d/apple_dcp/')
                core.require(relative.startswith(allowed), 'Unexpected supplement: '+relative)
                core.require(not file.is_symlink(), 'Unexpected supplement symlink')
                save_and_write(relative,file.read_bytes(),m['changed'])
            hook=core.restore_hook(m).replace('/usr/lib/asahi-external/boot-original.bin',
                                             '/'+backup_path)
            save_and_write(backup_path,original,m['changed'])
            save_and_write(hook_dir+'/restore.sh',hook,m['changed'],0o755)
            setup=dracut_setup(core.RELEASE,backup_path)
            save_and_write(hook_dir+'/module-setup.sh',setup,m['changed'],0o755)
            if m['os_id']=='fedora':
                core.run('restorecon','-RF','/lib/modules/'+core.RELEASE,boot/'dtbs'/core.RELEASE,
                         '/usr/lib/asahi-kernel-update','/'+hook_dir)
                for change in m['changed']:core.run('restorecon','-F','/'+change['path'])
            core.run('depmod','-a',core.RELEASE)
            core.run('dracut','--force','--no-hostonly','--no-hostonly-cmdline',
                     '--omit','asahi-kernel-update','--add',module,'--add-drivers','uas usb_storage '+m['root_fstype'],
                     boot/('initrd.img-'+core.RELEASE),core.RELEASE)
            core.verify_initramfs(Path('/'),boot,extra_modules=(m['root_fstype'],))
            if m['os_id']=='fedora':core.run('restorecon','-F',boot/('initrd.img-'+core.RELEASE))
            m['files']={name:core.digest(boot/name) for name in
                        ('Image-'+core.RELEASE,'initrd.img-'+core.RELEASE,'config-'+core.RELEASE)}
            generator='etc/grub.d/zz_asahi_kernel_update_'+m['root_uuid']+'_'+str(time.time_ns())
            save_and_write(generator,'#!/bin/sh\nexec tail -n +3 "$0"\n'+core.grub_entry(m),m['changed'],0o755)
            core.run(*m['commands']['rebuild'])
            core.run(m['commands']['check'],grub)
            core.require(core.grub_entry(m).strip() in grub.read_text(),'GRUB entry differs from manifest')
            verify_preserved_boot_selection(grub_before.decode(),grub.read_text(),core.grub_entry(m))
            core.require(all(core.digest(p)==h for p,h in before.items()),'Account database changed unexpectedly')
            lib=Path('/usr/local/lib/asahi-kernel-manager')
            core.atomic(lib/'install.py',Path(core.__file__).read_bytes())
            core.atomic(lib/'update.py',Path(__file__).read_bytes())
            core.atomic('/usr/local/sbin/asahi-kernel-update',
                        '#!/bin/sh\nexec python3 /usr/local/lib/asahi-kernel-manager/update.py "$@"\n',0o755)
            m.update(status='prepared-not-boot-tested',grub_sha=core.digest(grub))
            core.json_write(STATE/'manifest.json',m)
    except BaseException:
        restore_changed(m['changed'])
        core.atomic(grub,grub_before)
        m['status']='failed-new-version-files-may-remain'
        core.json_write(STATE/'manifest.json',m)
        raise
    finally:
        inhibitor.terminate();inhibitor.wait()
    os.sync()
    print('Prepared; original kernel remains default. No reboot performed.')
    print('Later: sudo asahi-kernel-update --arm --release '+core.RELEASE+'; then reboot manually.')


def arm(cancel=False):
    m=json.loads((STATE/'manifest.json').read_text())
    current=context()
    for key in ('os_id','root_uuid','system_boot_uuid','internal_esp_uuid'):
        core.require(current[key]==m[key], 'Boot context changed: '+key)
    core.require(m['status'] in ('prepared-not-boot-tested','boot-verified'),'Preparation did not finish')
    cmd=m['commands']; live=Path('/boot/efi/m1n1/boot.bin')
    marker=live.parent/('external-'+m['root_uuid']+'.armed')
    core.require(core.digest(STATE/'boot-original.bin')==m['original_sha'],'Backup changed')
    core.require(core.digest(live) in (m['original_sha'],m['candidate_sha']),'Unexpected active boot bundle')
    env=core.output(cmd['edit'],cmd['env'],'list')
    next_entries=core.pending_grub_entries(env)
    entry=m.get('entry_id','asahi-external-'+m['root_uuid'])
    expected='next_entry='+entry
    core.require(not next_entries or next_entries==[expected], 'Another boot selection is pending')
    if cancel:
        core.atomic(live,(STATE/'boot-original.bin').read_bytes())
        marker.unlink(missing_ok=True)
        core.run(cmd['edit'],cmd['env'],'unset','next_entry')
        os.sync();print('Original boot restored; prepared kernel files retained.');return
    preflight(m,space=False)
    for name,sha in m['files'].items():core.require(core.digest(Path(m['boot_directory'])/name)==sha,'Boot file changed: '+name)
    core.require(core.digest(STATE/'boot-candidate.bin')==m['candidate_sha'],'Candidate changed')
    core.require(core.grub_entry(m).strip() in Path(cmd['cfg']).read_text(),'Menu configuration changed')
    core.require(shutil.disk_usage(live.parent).free>=2*live.stat().st_size+2*1024**2,'ESP too full for safe staging')
    core.atomic(live.parent/'boot-before-kernel-update.bin',(STATE/'boot-original.bin').read_bytes())
    try:
        core.run(cmd['reboot'],entry)
        core.atomic(marker,m['candidate_sha']+'\n')
        core.atomic(live,(STATE/'boot-candidate.bin').read_bytes())
    except BaseException:
        core.atomic(live,(STATE/'boot-original.bin').read_bytes())
        marker.unlink(missing_ok=True)
        core.run(cmd['edit'],cmd['env'],'unset','next_entry')
        raise
    os.sync();print('One-time kernel start armed; not rebooted. Original boot bundle restores in initramfs.')


def verify_running():
    core.require(platform.release()==core.RELEASE, 'The prepared kernel is not running')
    m=json.loads((STATE/'manifest.json').read_text())
    current=context()
    for key in ('root_uuid','system_boot_uuid','internal_esp_uuid'):
        core.require(current[key]==m[key], 'Different installation is running: '+key)
    for name,sha in m['files'].items():
        core.require(core.digest(Path(m['boot_directory'])/name)==sha,'Boot file changed: '+name)
    live=Path('/boot/efi/m1n1/boot.bin')
    core.require(core.digest(live)==m['original_sha'],'Original boot bundle has not been restored')
    core.require(not (live.parent/('external-'+m['root_uuid']+'.armed')).exists(),'Boot marker remains armed')
    m.update(status='boot-verified',boot_validation=dict(
        utc=datetime.now(timezone.utc).isoformat(),
        boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        scope='Matching kernel/root/boot files and restored boot bundle only; no peripheral functional certification'))
    core.json_write(STATE/'manifest.json',m)
    print('Kernel boot verified; default unchanged. Peripheral errors must be assessed separately.')


def select_saved_state(release=None, running=False):
    global STATE
    if running:
        current = platform.release()
        core.require(release is None or release == current, '--release differs from running kernel')
        release = current
    if release is None:
        candidates = sorted(STATE_ROOT.glob('*/manifest.json'))
        core.require(len(candidates) == 1, 'Select the prepared kernel explicitly with --release VERSION')
        release = candidates[0].parent.name
    release = core.release_name(release)
    state = STATE_ROOT / release
    manifest = json.loads((state / 'manifest.json').read_text())
    core.require(manifest.get('release') == release and manifest.get('target') == 'internal-update',
                 'Saved update state does not match requested release')
    STATE, core.RELEASE = state, release
    # No network lookup here: boot/recovery always use the prepared version.


def main():
    global STATE
    p=argparse.ArgumentParser(description=__doc__)
    g=p.add_mutually_exclusive_group()
    g.add_argument('--plan',action='store_true')
    g.add_argument('--prepare',action='store_true')
    g.add_argument('--arm',action='store_true')
    g.add_argument('--cancel-boot',action='store_true')
    g.add_argument('--verify-running',action='store_true')
    p.add_argument('--allow-older',action='store_true',help='Explicitly permit preparing an older upstream version alongside newer kernels')
    p.add_argument('--kernel-tag', help='Pin a published build for --plan or --prepare')
    p.add_argument('--release', help='Prepared local version for --arm, --cancel-boot or --verify-running')
    a=p.parse_args()
    local_action = a.arm or a.cancel_boot or a.verify_running
    core.require(not a.kernel_tag or not local_action, '--kernel-tag cannot change a prepared boot')
    core.require(not a.release or local_action, '--release selects a saved update; use --kernel-tag for preparation')
    if not local_action:
        core.select_build(a.kernel_tag)
        STATE = STATE_ROOT / core.RELEASE
    core.require(not a.allow_older or a.prepare, '--allow-older requires --prepare')
    if a.prepare or a.arm or a.cancel_boot or a.verify_running:
        with core.exclusive_operation():
            if local_action:
                select_saved_state(a.release, running=a.verify_running)
            if a.prepare:prepare(a.allow_older)
            elif a.verify_running:verify_running()
            else:arm(a.cancel_boot)
    else:plan()


if __name__=='__main__':
    try:main()
    except (RuntimeError, ValueError, OSError, subprocess.CalledProcessError, KeyboardInterrupt) as exc:
        print('STOP:',exc,file=sys.stderr);sys.exit(1)
