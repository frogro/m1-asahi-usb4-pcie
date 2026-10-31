#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Experimental fresh external Ubuntu Asahi installer for Mac mini M1 (J274).
No writes without --install. --plan and --list-disks are read-only.
"""
import argparse
import contextlib
import getpass
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import struct
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import uuid
import zipfile

RELEASE = '7.2.12-usb4sd4-egpu2'
BUILD_COMMIT = '7b20516bd4be77bb885989e288754f56149898c4'
KERNEL_BASE = 'f7734f4c91c0f47d9e762786968057bec99a0788'
REPO = 'https://github.com/frogro/m1-asahi-usb4-pcie'
KERNEL_URL = REPO + '/releases/download/kernel-build-41155087907-1/linux-' + RELEASE + '-arm64.tar.zst'
KERNEL_SHA = '7b990cf7d8e975e9e65b196685a32ee012c4010fe5699c7ca3b382ceea69e17c'
IMAGE_URL = 'https://files3.tobhe.de/ubuntu/os/ubuntu-desktop-26.04-20260528.zip'
IMAGE_SHA = '00d2cc3f715df0c307f1e16cb09b8ea092f46a0d62ee89b33c551676ee4885e4'
GIB = 1024 ** 3
BASE = Path('/var/lib/asahi-external')
OPTIONS = ('rootwait rw console=tty0 panic=20 rd.retry=90 rd.timeout=120 '
           'rd.shell=0 rd.emergency=reboot '
           'pcie_apple_pciec.pciec_topology_events=1 '
           'pcie_apple_pciec.pciec_link_events=0 '
           'pcie_apple_pciec.pciec_reset_ack_clear=0 pciehp.pciehp_poll_mode=0 '
           'pci=hpbussize=16,hpmmiosize=32M,hpmmioprefsize=512M,realloc=on '
           'appledrm.dpin_autostart=1 appledrm.hdmi_audio=1 '
           'amdgpu.runpm=0 amdgpu.aspm=0 amdgpu.rebar=0')


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def run(*args, **kw):
    return subprocess.run([str(a) for a in args], check=True, **kw)


def output(*args):
    return run(*args, stdout=subprocess.PIPE, text=True).stdout.strip()


def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def atomic(path, data, mode=0o644):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as f:
            os.fchmod(f.fileno(), mode)
            f.write(data.encode() if isinstance(data, str) else data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        d = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(d)
        finally:
            os.close(d)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def json_write(path, obj):
    atomic(path, json.dumps(obj, indent=2) + '\n', 0o600)


def uuid_ok(value):
    require(bool(re.fullmatch(r'[A-Fa-f0-9-]{8,36}', value)), 'Invalid filesystem UUID')
    return value


def safe_label(value):
    # Never interpolate raw firmware/device strings into a GRUB program.
    return re.sub(r'[^A-Za-z0-9 ._+()-]', '_', value).strip()[:70] or 'USB disk'


def walk(node):
    yield node
    for child in node.get('children', []):
        yield from walk(child)


def disk_reasons(disk):
    reasons = []
    if disk['type'] != 'disk' or disk.get('tran') != 'usb':
        reasons.append('not a USB whole disk (Thunderbolt-only boot is unsupported)')
    if disk.get('ro') or int(disk['size']) < 32 * GIB:
        reasons.append('read-only or smaller than 32 GiB')
    if not (disk.get('serial') or '').strip():
        reasons.append('no unique hardware serial available')
    for node in walk(disk):
        if any(node.get('mountpoints') or []):
            reasons.append('mounted filesystem or active swap')
        if node['type'] not in ('disk', 'part'):
            reasons.append('active device-mapper/RAID child')
        holders = Path('/sys/class/block') / Path(node['path']).name / 'holders'
        if holders.exists() and any(holders.iterdir()):
            reasons.append('active block-device holders')
    return sorted(set(reasons))


def disks():
    data = json.loads(output('lsblk', '--json', '--bytes', '--paths', '-o',
                            'NAME,PATH,TYPE,TRAN,SIZE,MODEL,SERIAL,RO,MOUNTPOINTS,MAJ:MIN'))
    return [d for d in data['blockdevices'] if d['type'] == 'disk']


def identity(d):
    return {k: d.get(k) for k in ('path', 'maj:min', 'size', 'model', 'serial', 'tran')}


def choose_disk(device=None):
    available = disks()
    for i, d in enumerate(available, 1):
        why = disk_reasons(d)
        print(f"{i}. {safe_label(d.get('model') or '')} | {int(d['size'])/GIB:.1f} GiB | "
              f"{d['path']} | serial {safe_label(d.get('serial') or '')} | "
              + ('BLOCKED: ' + '; '.join(why) if why else 'available'))
    if device:
        matches = [d for d in available if Path(d['path']).resolve() == Path(device).resolve()]
        require(len(matches) == 1, 'Target not found as a whole disk')
        chosen = matches[0]
    else:
        n = int(input('Target number: '))
        require(1 <= n <= len(available), 'Invalid selection')
        chosen = available[n - 1]
    require(not disk_reasons(chosen), '; '.join(disk_reasons(chosen)))
    require(sum(d.get('serial') == chosen.get('serial') for d in available) == 1,
            'Hardware serial is shared by multiple disks; disconnect the ambiguous devices')
    return chosen


def recheck_disk(original):
    matches = [d for d in disks() if d['path'] == original['path']]
    require(len(matches) == 1 and identity(matches[0]) == identity(original),
            'Disk identity changed; refusing to write')
    require(not disk_reasons(matches[0]), 'Target became mounted or busy')


def pending_grub_entries(environment):
    # GRUB consumes a one-shot selection by writing an empty next_entry.
    return [line for line in environment.splitlines()
            if line.startswith('next_entry=') and line.split('=', 1)[1].strip()]


def boot_options(m):
    result = OPTIONS
    if m.get('os_id', 'ubuntu') == 'fedora':
        result += ' lsm=landlock,lockdown,yama,integrity,selinux,bpf'
    subvol = m.get('root_subvolume', '/')
    require(bool(re.fullmatch(r'/[A-Za-z0-9_/.-]*', subvol)), 'Unsupported root subvolume name')
    if subvol != '/':
        result += ' rootflags=subvol=' + subvol.lstrip('/')
    return result


def grub_entry(m):
    boot, root, esp = (uuid_ok(m[k]) for k in ('boot_uuid', 'root_uuid', 'internal_esp_uuid'))
    rel = m['release']
    require(bool(re.fullmatch(r'[A-Za-z0-9._+-]+', rel)), 'Invalid kernel release')
    prefix=m.get('boot_prefix', '')
    require(prefix == '' or (bool(re.fullmatch(r'/[A-Za-z0-9_./+-]+', prefix))
                            and '..' not in Path(prefix).parts), 'Invalid GRUB boot directory')
    entry = 'asahi-external-' + root
    os_name = 'Fedora Asahi Remix' if m.get('os_id') == 'fedora' else 'Ubuntu Asahi'
    arm_command = 'sudo asahi-kernel-update --arm' if m.get('target') == 'internal-update' else 'sudo asahi-external-boot --arm ' + root
    name = f"{os_name} {rel} - {safe_label(m['model'])} ({root[:8]})"
    return f'''menuentry '{name}' --id {entry} {{
    insmod part_gpt
    insmod fat
    insmod ext2
    insmod search_fs_uuid
    if search --no-floppy --fs-uuid --set=systemesp {esp}; then
      if [ -f ($systemesp)/m1n1/external-{root}.armed ]; then
        if search --no-floppy --fs-uuid --set=externalboot {boot}; then
          linux ($externalboot){prefix}/Image-{rel} root=UUID={root} {boot_options(m)}
          initrd ($externalboot){prefix}/initrd.img-{rel}
        else
          echo 'Configured boot filesystem not found. Check the selected installation medium.'
          sleep --interruptible 15
        fi
      else
        echo 'First run: {arm_command}'
        sleep --interruptible 15
      fi
    fi
}}
'''


def replace_dtb(bundle, replacement):
    """Replace the one raw J274 FDT in an existing m1n1/U-Boot bundle."""
    magic = b'\xd0\x0d\xfe\xed'
    candidates = []
    pos = 0
    with tempfile.TemporaryDirectory() as td:
        dtb = Path(td) / 'test.dtb'
        def compatible(blob):
            dtb.write_bytes(blob)
            p = subprocess.run(['fdtget', str(dtb), '/', 'compatible'],
                               capture_output=True, text=True)
            return p.returncode == 0 and 'apple,j274' in p.stdout.split()
        require(len(replacement) >= 40 and replacement[:4] == magic and
                struct.unpack('>I', replacement[4:8])[0] == len(replacement) and
                compatible(replacement), 'Replacement is not a valid J274 DTB')
        while True:
            pos = bundle.find(magic, pos)
            if pos < 0:
                break
            if pos + 40 <= len(bundle):
                size = struct.unpack('>I', bundle[pos+4:pos+8])[0]
                if 40 <= size <= len(bundle) - pos and compatible(bundle[pos:pos+size]):
                    candidates.append((pos, size))
            pos += 4
    require(len(candidates) == 1, 'Expected exactly one embedded J274 DTB; no bundle changed')
    pos, size = candidates[0]
    return bundle[:pos] + replacement + bundle[pos+size:]


def host_check():
    require(os.geteuid() == 0, 'Use sudo for installation/boot preparation')
    require(platform.machine() == 'aarch64', 'Installation must run on the target M1 Mac')
    compatible = Path('/proc/device-tree/compatible').read_bytes().split(b'\0')
    require(b'apple,j274' in compatible and b'apple,t8103' in compatible,
            'This experimental installer supports Mac mini M1/J274 only')
    require('ID=ubuntu\n' in Path('/etc/os-release').read_text(),
            'Run from the original internal Ubuntu Asahi installation')
    require(output('findmnt', '-n', '-o', 'SOURCE', '/') .startswith('/dev/nvme'),
            'Run from internal Ubuntu; an external root is not supported as installation host')
    required = ('sgdisk', 'mkfs.vfat', 'mkfs.ext4', 'e2fsck', 'resize2fs', 'tune2fs',
                'udevadm', 'mount', 'umount', 'chroot', 'rsync', 'depmod', 'fdtget',
                'modinfo', 'systemd-inhibit', 'systemctl', 'zstd', 'tar', 'grub-script-check', 'update-grub', 'grub-reboot',
                'grub-editenv', 'blkid', 'lsinitrd', 'blockdev')
    missing = [x for x in required if not shutil.which(x)]
    require(not missing, 'Missing host commands: ' + ', '.join(missing))
    require(Path('/boot/grub/grub.cfg').is_file(), 'Internal GRUB configuration missing')
    esp = uuid_ok(output('findmnt', '-n', '-o', 'UUID', '--mountpoint', '/boot/efi'))
    require(Path('/boot/efi/m1n1/boot.bin').is_file(), 'Internal m1n1 bundle missing')
    needed = 2 * Path('/boot/efi/m1n1/boot.bin').stat().st_size + 2 * 1024**2
    require(shutil.disk_usage('/boot/efi').free >= needed,
            'Internal ESP needs space for backup and atomic staging (at least ' + str(needed) + ' bytes)')
    require(not list(Path('/boot/efi/m1n1').glob('*.armed')) and
            not Path('/boot/efi/m1n1/usb-test-armed').exists(), 'A test boot is already armed')
    require(Path('/lib/firmware/vendor/apple').is_dir(), 'Local Apple vendor firmware missing')
    require(Path('/boot/efi/asahi/all_firmware.tar.gz').is_file(), 'Local firmware archive missing')
    require(Path('/boot/efi/vendorfw/firmware.cpio').is_file(), 'Bootloader vendor firmware archive missing')
    require(not pending_grub_entries(output('grub-editenv', '/boot/grub/grubenv', 'list')),
            'Another one-time GRUB selection is pending')
    return esp


def download(url, sha, path):
    require(re.fullmatch('[a-f0-9]{64}', sha), 'Asset has no pinned SHA-256')
    if path.exists():
        require(digest(path) == sha, f'Checksum mismatch: {path}; remove it before retrying')
        return path
    print('Downloading:', url, flush=True)
    tmp = path.with_suffix(path.suffix + '.partial')
    with urllib.request.urlopen(url, timeout=60) as src, tmp.open('wb') as dst:
        shutil.copyfileobj(src, dst, 1024 * 1024)
    require(digest(tmp) == sha, f'Checksum mismatch: {tmp}')
    tmp.replace(path)
    return path


@contextlib.contextmanager
def mounted(source, target, *options):
    target = Path(target)
    target.mkdir(parents=True, exist_ok=True)
    run('mount', *options, source, target)
    try:
        yield target
    finally:
        run('umount', '-R', target)  # Never lazy-unmount a partly written installation.


def write_image(z, member, device):
    require(z.getinfo(member).file_size <= int(output('blockdev', '--getsize64', device)),
            'Image is larger than its target partition')
    with z.open(member) as src, open(device, 'wb', buffering=0) as dst:
        shutil.copyfileobj(src, dst, 4 * 1024 * 1024)
        os.fsync(dst.fileno())
    # e2fsck returns 1 when it repaired a filesystem successfully.
    r = subprocess.run(['e2fsck', '-fy', device])
    require(r.returncode in (0, 1), 'Image filesystem check failed')
    run('tune2fs', '-U', 'random', device)
    run('resize2fs', device)


def restore_hook(m):
    root = uuid_ok(m['root_uuid'])
    esp = uuid_ok(m['internal_esp_uuid'])
    return f'''#!/bin/sh
restore_external_bundle() {{
    [ -e /run/asahi-external-restored ] && return 0
    modprobe nvme_apple 2>/dev/null || :
    disk=$(blkid -U {esp} 2>/dev/null) || return 0
    [ -n "$disk" ] || return 0
    mkdir -p /run/asahi-original-esp
    mount -t vfat -o rw "$disk" /run/asahi-original-esp || return 0
    base=/run/asahi-original-esp/m1n1
    if [ -f "$base/external-{root}.armed" ]; then
        current=$(sha256sum "$base/boot.bin" | cut -d ' ' -f1)
        saved=$(sha256sum /usr/lib/asahi-external/boot-original.bin | cut -d ' ' -f1)
        if [ "$current" = {m['candidate_sha']} ] && [ "$saved" = {m['original_sha']} ]; then
            if cp /usr/lib/asahi-external/boot-original.bin "$base/external-restore.tmp"; then
                sync
                if mv "$base/external-restore.tmp" "$base/boot.bin"; then
                    sync
                    rm -f "$base/external-{root}.armed"
                    touch /run/asahi-external-restored
                fi
            fi
        elif [ "$current" = {m['original_sha']} ]; then
            rm -f "$base/external-{root}.armed"
            touch /run/asahi-external-restored
        else
            echo 'ASAHI EXTERNAL: unexpected boot bundle, refusing overwrite' >&2
        fi
    fi
    sync
    umount /run/asahi-original-esp
}}
restore_external_bundle
'''


def verify_initramfs(root, boot, extra_modules=()):
    listing = output('lsinitrd', boot / ('initrd.img-' + RELEASE))
    for required in ('restore.sh', 'boot-original.bin'):
        require(required in listing, 'Initramfs lacks ' + required)
    require(RELEASE in listing, 'Initramfs has no matching module tree')
    for module in ('uas', 'usb_storage', 'sd_mod', 'xhci_hcd', 'ext4', 'nvme_apple') + tuple(extra_modules):
        filename = output('modinfo', '-b', root, '-k', RELEASE, '-F', 'filename', module)
        if filename != '(builtin)':
            require(Path(filename).name in listing, 'Initramfs lacks required driver: ' + module)
    require((root / 'lib/firmware/apple/avd-fw-v3-t0.bin').is_file(), 'AVD firmware missing')
    vermagic = output('modinfo', '-b', root, '-k', RELEASE, '-F', 'vermagic', 'amdgpu')
    require(vermagic.split()[0] == RELEASE, 'AMDGPU module does not match the kernel')


def configure_root(root, boot, esp, m, username, password, fw_source):
    # The only host data copied are machine firmware and the boot fallback binary.
    run('rsync', '-a', '--', fw_source, str(root / 'lib/firmware/vendor') + '/')
    shutil.copyfile('/boot/efi/asahi/all_firmware.tar.gz', esp / 'all_firmware.tar.gz')
    (esp / 'asahi').mkdir(exist_ok=True)
    (esp / 'all_firmware.tar.gz').replace(esp / 'asahi/all_firmware.tar.gz')
    atomic(root / 'etc/fstab',
           f"UUID={m['root_uuid']} / ext4 defaults 0 1\n"
           f"UUID={m['boot_uuid']} /boot ext4 defaults 0 2\n"
           f"UUID={m['esp_uuid']} /boot/efi vfat umask=0077 0 2\n")
    atomic(root / 'etc/hostname', 'asahi-external\n')
    atomic(root / 'etc/hosts', '127.0.0.1 localhost\n127.0.1.1 asahi-external\n::1 localhost ip6-localhost\n')
    atomic(root / 'etc/cloud/cloud-init.disabled', '')
    atomic(root / 'etc/machine-id', '')
    (root / 'var/lib/dbus/machine-id').unlink(missing_ok=True)
    (root / 'var/lib/systemd/random-seed').unlink(missing_ok=True)
    for key in (root / 'etc/ssh').glob('ssh_host_*'):
        key.unlink()
    require(not list((root / 'home').iterdir()), 'Pristine image unexpectedly contains user homes')
    users = (root / 'etc/passwd').read_text().splitlines()
    require(not any(1000 <= int(u.split(':')[2]) < 65534 for u in users),
            'Pristine image unexpectedly contains personal users')
    atomic(root / 'usr/lib/asahi-external/boot-original.bin',
           (BASE / m['root_uuid'] / 'boot-original.bin').read_bytes())
    mod = root / 'usr/lib/dracut/modules.d/91asahi-external'
    atomic(mod / 'restore.sh', restore_hook(m), 0o755)
    atomic(mod / 'module-setup.sh', '''#!/bin/bash
check() { return 0; }
depends() { echo fs-lib; }
installkernel() { instmods nvme_apple vfat; }
install() {
    inst_multiple blkid mount umount modprobe sha256sum cut cp mv rm mkdir sync touch
    inst_simple /usr/lib/asahi-external/boot-original.bin
    inst_hook initqueue/settled 05 "$moddir/restore.sh"
    inst_hook pre-mount 05 "$moddir/restore.sh"
}
''', 0o755)
    atomic(root / 'etc/dracut.conf.d/91-asahi-external.conf', '''hostonly="no"
hostonly_cmdline="no"
add_drivers+=" usb_storage uas xhci_pci xhci_plat_hcd sd_mod ext4 "
force_drivers+=" usbhid xhci_hcd "
add_dracutmodules+=" asahi-external "
fw_dir+=" /lib/firmware/vendor "
''')
    # No services may start in the installation chroot.
    policy = root / 'usr/sbin/policy-rc.d'
    old_policy = policy.read_bytes() if policy.exists() else None
    atomic(policy, '#!/bin/sh\nexit 101\n', 0o755)
    try:
        with contextlib.ExitStack() as stack:
            for path in ('dev', 'proc', 'sys'):
                stack.enter_context(mounted('/' + path, root / path, '--rbind'))
                run('mount', '--make-rslave', root / path)
            # A private /run avoids exposing the host systemd and D-Bus sockets.
            stack.enter_context(mounted('tmpfs', root / 'run', '-t', 'tmpfs'))
            run('chroot', root, 'useradd', '-m', '-s', '/bin/bash', '-G', 'sudo,video,render,audio', username)
            run('chroot', root, 'chpasswd', input=f'{username}:{password}\n', text=True)
            run('chroot', root, 'passwd', '-l', 'root')
            # This is an installed desktop, not the distributor's OEM setup session.
            run('chroot', root, 'systemctl', 'mask', 'oem-config.service')
            run('chroot', root, 'systemctl', 'set-default', 'graphical.target')
            run('chroot', root, 'depmod', '-a', RELEASE)
            run('chroot', root, 'dracut', '--force', '--no-hostonly', '--kver', RELEASE,
                '/boot/initrd.img-' + RELEASE)
    finally:
        if old_policy is None:
            policy.unlink(missing_ok=True)
        else:
            atomic(policy, old_policy, 0o755)
    verify_initramfs(root, boot)
    # Avoid an image-supplied GRUB configuration booting its old hardcoded UUIDs.
    atomic(boot / 'grub/grub.cfg', grub_entry(m))


def install_unlocked(args):
    internal_esp = host_check()
    print('1. Ubuntu Asahi Desktop 26.04 (experimental, fresh installation)')
    print('Fedora Asahi Remix: not yet enabled; no validated image/kernel integration.')
    require(input('OS number [1]: ').strip() in ('', '1'), 'Unsupported distribution')
    disk = choose_disk(args.device)
    username = input('New username: ').strip()
    require(bool(re.fullmatch('[a-z][a-z0-9_-]{0,30}', username)) and username != 'root', 'Invalid username')
    password = getpass.getpass('New password (not copied from host): ')
    require(len(password) >= 8 and not any(ord(c) < 32 for c in password) and ':' not in password,
            'Use at least eight characters, without newline or colon')
    require(password == getpass.getpass('Repeat password: '), 'Passwords differ')
    cache = Path(args.cache).resolve()
    cache.mkdir(parents=True, exist_ok=True, mode=0o700)
    require(cache.stat().st_uid == 0 and not cache.stat().st_mode & 0o022,
            'Cache must be root-owned and not writable by other users')
    require(shutil.disk_usage(cache).free >= 6 * GIB, 'Need at least 6 GiB free download space')
    image = download(IMAGE_URL, IMAGE_SHA, cache / 'ubuntu-asahi.zip')
    kernel = download(KERNEL_URL, KERNEL_SHA, cache / ('linux-' + RELEASE + '.tar.zst'))
    with zipfile.ZipFile(image) as z:
        require({'boot.img', 'root.img'} <= set(z.namelist()), 'Unexpected distribution image layout')
        require(z.getinfo('boot.img').file_size <= 3 * GIB and
                z.getinfo('root.img').file_size <= int(disk['size']) - 5 * GIB,
                'Image does not fit selected disk')
    # Validate boot-bundle compatibility before the first destructive operation.
    with tempfile.TemporaryDirectory() as td:
        run('tar', '--zstd', '-xf', kernel, '-C', td,
            './boot/dtbs/' + RELEASE + '/apple/t8103-j274.dtb')
        original = Path('/boot/efi/m1n1/boot.bin').read_bytes()
        candidate = replace_dtb(original, (Path(td) / 'boot/dtbs' / RELEASE / 'apple/t8103-j274.dtb').read_bytes())
    print('\nERASE ALL DATA:', safe_label(disk.get('model') or ''), disk['path'], disk['serial'])
    phrase = 'ERASE ' + disk['serial'].strip()
    require(input('Type exactly ' + phrase + ': ') == phrase, 'Cancelled; no disk changed')
    recheck_disk(disk)
    run('sgdisk', '--zap-all', disk['path'])
    run('sgdisk', '-n', '1:0:+512M', '-t', '1:ef00', '-c', '1:Asahi external ESP',
        '-n', '2:0:+3G', '-t', '2:8300', '-c', '2:Asahi external boot',
        '-n', '3:0:0', '-t', '3:8300', '-c', '3:Asahi external root', disk['path'])
    run('udevadm', 'settle')
    sep = 'p' if disk['path'][-1].isdigit() else ''
    p1, p2, p3 = [disk['path'] + sep + str(n) for n in (1, 2, 3)]
    run('mkfs.vfat', '-F', '32', '-n', 'ASAHI_ESP', p1)
    with zipfile.ZipFile(image) as z:
        write_image(z, 'boot.img', p2)
        write_image(z, 'root.img', p3)
    run('udevadm', 'settle')
    m = dict(release=RELEASE, build_commit=BUILD_COMMIT, kernel_base=KERNEL_BASE,
             image_url=IMAGE_URL, image_sha256=IMAGE_SHA, kernel_sha256=KERNEL_SHA, model=disk.get('model') or 'USB disk', disk=identity(disk),
             root_uuid=uuid_ok(output('blkid', '-s', 'UUID', '-o', 'value', p3)),
             boot_uuid=uuid_ok(output('blkid', '-s', 'UUID', '-o', 'value', p2)),
             esp_uuid=uuid_ok(output('blkid', '-s', 'UUID', '-o', 'value', p1)),
             internal_esp_uuid=internal_esp, original_sha=hashlib.sha256(original).hexdigest(),
             candidate_sha=hashlib.sha256(candidate).hexdigest(), status='incomplete')
    state = BASE / m['root_uuid']
    state.mkdir(parents=True, mode=0o700)
    atomic(state / 'boot-original.bin', original)
    atomic(state / 'boot-candidate.bin', candidate)
    json_write(state / 'manifest.json', m)
    with tempfile.TemporaryDirectory(prefix='asahi-install-', dir='/mnt') as td:
        with mounted(p3, td) as root, mounted(p2, root / 'boot') as boot, mounted(p1, boot / 'efi') as esp:
            run('tar', '--zstd', '-xf', kernel, '-C', root, '--no-same-owner', '--keep-directory-symlink')
            configure_root(root, boot, esp, m, username, password, '/lib/firmware/vendor/')
            m['files'] = {name: digest(boot / name) for name in
                          ('Image-' + RELEASE, 'initrd.img-' + RELEASE, 'config-' + RELEASE)}
            m['dtb_sha'] = digest(boot / 'dtbs' / RELEASE / 'apple/t8103-j274.dtb')
            run('grub-script-check', boot / 'grub/grub.cfg')
    # Only now add a menu entry to the original installation. Preserve its default.
    path = Path('/etc/grub.d/42_asahi_external_' + m['root_uuid'])
    require(not path.exists(), 'GRUB generator already exists')
    atomic(state / 'grub.cfg.before', Path('/boot/grub/grub.cfg').read_bytes())
    try:
        atomic(path, '#!/bin/sh\nexec tail -n +3 "$0"\n' + grub_entry(m), 0o755)
        run('update-grub')
        run('grub-script-check', '/boot/grub/grub.cfg')
        require(grub_entry(m).strip() in Path('/boot/grub/grub.cfg').read_text(), 'Generated entry differs')
    except BaseException:
        path.unlink(missing_ok=True)
        atomic('/boot/grub/grub.cfg', (state / 'grub.cfg.before').read_bytes())
        raise
    atomic('/usr/local/sbin/asahi-external-boot', Path(__file__).read_bytes(), 0o755)
    m['status'] = 'prepared-not-boot-tested'
    json_write(state / 'manifest.json', m)
    os.sync()
    print('\nFresh system prepared. Nothing rebooted; original boot remains active.')
    print('Check:', 'sudo asahi-external-boot --check ' + m['root_uuid'])
    print('One-time start:', 'sudo asahi-external-boot --arm ' + m['root_uuid'])
    print('Then reboot manually with the SSD connected DIRECTLY to a Mac USB-C port.')


def install(args):
    host_check()
    # Runtime masks disappear at the next boot even after a power failure.
    was_active = subprocess.run(['systemctl', 'is-active', '--quiet', 'udisks2.service']).returncode == 0
    previous = subprocess.run(['systemctl', 'is-enabled', 'udisks2.service'],
                              capture_output=True, text=True).stdout.strip()
    changed_mask = not previous.startswith('masked')
    inhibitor = subprocess.Popen(['systemd-inhibit', '--what=sleep:shutdown', '--mode=block',
                                  '--why=Preparing external Asahi installation', 'sleep', 'infinity'])
    try:
        if changed_mask:
            run('systemctl', 'mask', '--runtime', '--now', 'udisks2.service')
        require(inhibitor.poll() is None, 'Could not inhibit sleep during installation')
        install_unlocked(args)
    finally:
        if changed_mask:
            run('systemctl', 'unmask', '--runtime', 'udisks2.service')
            if was_active:
                run('systemctl', 'start', 'udisks2.service')
        inhibitor.terminate()
        inhibitor.wait()


def boot_action(root_uuid, arm=False):
    host_check()
    root_uuid = uuid_ok(root_uuid)
    state = BASE / root_uuid
    m = json.loads((state / 'manifest.json').read_text())
    require(m['status'] == 'prepared-not-boot-tested', 'Installation incomplete')
    require(m['root_uuid'] == root_uuid, 'Manifest/target mismatch')
    require(m['internal_esp_uuid'] == output('findmnt', '-n', '-o', 'UUID', '--mountpoint', '/boot/efi'), 'Wrong internal ESP')
    for name, expected in (('boot-original.bin', m['original_sha']), ('boot-candidate.bin', m['candidate_sha'])):
        require(digest(state / name) == expected, 'Boot backup/candidate changed')
    live = Path('/boot/efi/m1n1/boot.bin')
    require(digest(live) == m['original_sha'], 'Internal bundle changed; reinstallation/revalidation required')
    require(grub_entry(m).strip() in Path('/boot/grub/grub.cfg').read_text(), 'GRUB parameters differ from manifest')
    run('grub-script-check', '/boot/grub/grub.cfg')
    with tempfile.TemporaryDirectory(dir='/run') as td:
        with mounted('/dev/disk/by-uuid/' + m['boot_uuid'], td, '-o', 'ro,noload') as boot:
            for name, sha in m['files'].items():
                require(digest(boot / name) == sha, 'External boot file changed: ' + name)
            require(digest(boot / 'dtbs' / RELEASE / 'apple/t8103-j274.dtb') == m['dtb_sha'], 'DTB changed')
    require(Path('/dev/disk/by-uuid/' + root_uuid).exists(), 'External root filesystem missing')
    if not arm:
        print('Kernel, initramfs, UUIDs, DTB, GRUB options and original boot backup verified.')
        return
    marker = live.parent / ('external-' + root_uuid + '.armed')
    atomic(live.parent / 'boot-before-external.bin', (state / 'boot-original.bin').read_bytes())
    try:
        run('grub-reboot', 'asahi-external-' + root_uuid)
        atomic(marker, m['candidate_sha'] + '\n')
        atomic(live, (state / 'boot-candidate.bin').read_bytes())
    except BaseException:
        atomic(live, (state / 'boot-original.bin').read_bytes())
        marker.unlink(missing_ok=True)
        run('grub-editenv', '/boot/grub/grubenv', 'unset', 'next_entry')
        raise
    os.sync()
    print('One-time external boot armed; not rebooted. Initramfs restores the original bundle.')
    print('Recovery before initramfs starts is NOT guaranteed. Keep the saved boot bundle accessible.')


@contextlib.contextmanager
def exclusive_operation():
    require(os.geteuid() == 0, 'Use sudo for this operation')
    with open('/run/lock/asahi-external.lock', 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        require(hasattr(os, 'unshare'), 'Python 3.12 or newer with mount namespace support is required')
        os.unshare(os.CLONE_NEWNS)
        run('mount', '--make-rprivate', '/')
        yield


def disarm(root_uuid):
    root_uuid = uuid_ok(root_uuid)
    state = BASE / root_uuid
    m = json.loads((state / 'manifest.json').read_text())
    require(output('findmnt', '-n', '-o', 'UUID', '--mountpoint', '/boot/efi') == m['internal_esp_uuid'],
            'Run recovery from the original internal Ubuntu with its ESP mounted')
    live = Path('/boot/efi/m1n1/boot.bin')
    require(digest(state / 'boot-original.bin') == m['original_sha'], 'Backup hash changed')
    require(digest(live) in (m['original_sha'], m['candidate_sha']), 'Unknown active bundle; refusing overwrite')
    env = output('grub-editenv', '/boot/grub/grubenv', 'list')
    next_entries = pending_grub_entries(env)
    require(not next_entries or next_entries == ['next_entry=asahi-external-' + root_uuid],
            'A different one-time boot is pending; refusing to change it')
    atomic(live, (state / 'boot-original.bin').read_bytes())
    (live.parent / ('external-' + root_uuid + '.armed')).unlink(missing_ok=True)
    run('grub-editenv', '/boot/grub/grubenv', 'unset', 'next_entry')
    os.sync()
    print('Original internal boot bundle restored; one-time external selection cancelled.')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    group = p.add_mutually_exclusive_group()
    group.add_argument('--list-disks', action='store_true')
    group.add_argument('--plan', action='store_true')
    group.add_argument('--install', action='store_true')
    group.add_argument('--check', metavar='ROOT_UUID')
    group.add_argument('--arm', metavar='ROOT_UUID')
    group.add_argument('--disarm', metavar='ROOT_UUID')
    p.add_argument('--device', help='Whole USB disk, e.g. /dev/disk/by-id/usb-...')
    p.add_argument('--cache', default='/var/cache/asahi-external')
    args = p.parse_args()
    if args.check or args.arm or args.disarm or args.install:
        with exclusive_operation():
            if args.disarm:
                disarm(args.disarm)
            elif args.install:
                install(args)
            else:
                boot_action(args.check or args.arm, bool(args.arm))
    elif args.list_disks:
        for d in disks():
            print(json.dumps(dict(identity(d), blocked=disk_reasons(d))))
    else:
        print('READ-ONLY PLAN. No installation, partitioning, boot change or download.')
        print('Ubuntu Asahi Desktop 26.04, fresh official image; kernel ' + RELEASE)
        print('Fedora Asahi Remix is not enabled in this first version.')
        print('USB-only target, >=32 GiB; EFI 512 MiB + boot 3 GiB + root remainder.')
        print('New user/password; no inherited personal data, keys or network passwords.')
        print('Only local machine firmware and an original boot-bundle backup are copied.')
        if args.device:
            d = choose_disk(args.device)
            print('Proposed boot title:', 'Ubuntu Asahi ' + RELEASE + ' - ' + safe_label(d.get('model') or 'USB disk') + ' (new UUID)')
        print('Install later on internal Ubuntu Asahi: sudo python3 install.py --install')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError, OSError, subprocess.CalledProcessError, KeyboardInterrupt) as exc:
        print('STOP:', exc, file=sys.stderr)
        sys.exit(1)
