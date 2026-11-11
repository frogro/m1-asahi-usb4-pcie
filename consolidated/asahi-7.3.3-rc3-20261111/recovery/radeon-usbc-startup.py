#!/usr/bin/python3
"""rc3 candidate: bounded recovery for the identified Navi21 USB-C path."""
import os
import json
from pathlib import Path
import subprocess
import sys
import time


class Recovery:
    def __init__(self, root=Path('/sys'), writer=None, waiter=None, bridge_probe=None):
        self.root = root
        self.gpu = root / 'bus/pci/devices/0002:05:00.0'
        self.pci = root / 'bus/pci/devices/0002:05:00.3'
        self.driver = root / 'bus/i2c/drivers/ucsi_ccg'
        self.write = writer or self.write_bounded
        self.wait = waiter or self.wait_bounded
        self.client = None
        self.bridge_probe = bridge_probe or self.read_bridge_bounded

    @staticmethod
    def log(message):
        print(message, flush=True)

    @staticmethod
    def read(path):
        try:
            return path.read_text().strip()
        except OSError:
            return ''

    @staticmethod
    def write_bounded(path, value):
        # A child process bounds potentially blocking sysfs/debugfs writes.
        subprocess.run([sys.executable, '-c',
                        'from pathlib import Path; import sys; '
                        'Path(sys.argv[1]).write_text(sys.argv[2])',
                        str(path), value + '\n'], check=True, timeout=20)

    @staticmethod
    def wait_bounded(predicate, seconds):
        deadline = time.monotonic() + seconds
        while True:
            result = predicate()
            if result:
                return result
            if time.monotonic() >= deadline:
                return None
            time.sleep(1)

    def connected(self):
        for connector in sorted(self.gpu.glob('drm/card[0-9]*/card*-DP-*')):
            if self.read(connector / 'status') == 'connected':
                return connector
        return None

    def discover_client(self):
        physical = self.pci.resolve()
        matches = [p for p in self.driver.glob('*-0008')
                   if p.is_symlink() and p.resolve().is_relative_to(physical)]
        if len(matches) == 1:
            self.client = matches[0]
            return self.client
        return None

    def port(self):
        if not self.client:
            return None
        ports = list(self.client.glob('typec/port[0-9]*'))
        return ports[0] if len(ports) == 1 else None

    def dp_partner(self):
        port = self.port()
        if not port:
            return None
        partner = port / (port.name + '-partner')
        for svid in partner.glob('*/svid'):
            if self.read(svid).lower().removeprefix('0x') == 'ff01':
                return partner
        return None

    def partner_or_done(self):
        if self.connected():
            return 'connected'
        if self.hardware_ready() != 'ready':
            return 'gone'
        if self.dp_partner():
            return 'partner'
        return None

    def hardware_ready(self):
        # Wait for PCI enumeration and DRM connector registration before deciding.
        gpu_id = self.read(self.gpu / 'device')
        pci_id = self.read(self.pci / 'device')
        if gpu_id and gpu_id != '0x73bf' or pci_id and pci_id != '0x73a4':
            return 'wrong-hardware'
        for device in (self.gpu, self.pci):
            vendor = self.read(device / 'vendor')
            if vendor and vendor != '0x1002':
                return 'wrong-hardware'
        if gpu_id == '0x73bf' and pci_id == '0x73a4' and any(
                self.read(p / 'status') in {'connected', 'disconnected'}
                for p in self.gpu.glob('drm/card[0-9]*/card*-DP-*')):
            return 'ready'
        return None

    def read_bridge_bounded(self):
        # Read only the known Radeon DP bridge, with a bounded child process.
        for aux in sorted((self.root / 'class/drm_dp_aux_dev').glob('*')):
            connector = (aux / 'device').resolve()
            if not connector.is_relative_to(self.gpu.resolve()):
                continue
            if '-DP-' not in connector.name:
                continue
            try:
                result = subprocess.run(
                    [sys.executable, __file__, '--bridge-sample', aux.name],
                    capture_output=True, text=True, timeout=3, check=True)
                data = json.loads(result.stdout)
            except (OSError, subprocess.SubprocessError, ValueError):
                continue
            if data.get('identity') == '00e04c4470312e3400':
                data['connector'] = str(connector)
                return data
        return None

    @staticmethod
    def known_bad_bridge(data):
        return bool(data and data.get('identity') == '00e04c4470312e3400'
                    and data.get('branch') and data.get('ports') == 0
                    and data.get('sinks') == 0)

    def renegotiated(self):
        data = self.bridge_probe()
        if (data and data.get('identity') == '00e04c4470312e3400'
                and data.get('ports', 0) > 0 and data.get('sinks', 0) > 0
                and self.connected()):
            return data
        return None

    def run(self):
        if self.wait(self.hardware_ready, 45) != 'ready':
            self.log('SKIP: tested Radeon hardware/DRM not ready; no changes')
            return 0
        expected = [(self.gpu, '0x73bf'), (self.pci, '0x73a4')]
        if any(self.read(p / 'vendor') != '0x1002' or
               self.read(p / 'device') != device for p, device in expected):
            self.log('SKIP: tested Radeon GPU/controller not present at expected PCI addresses')
            return 0
        if self.connected():
            self.log('SKIP: Radeon DP monitor already connected; no changes')
            return 0
        if not self.wait(self.discover_client, 20):
            self.log('SKIP: no unique UCSI client under the Radeon controller')
            return 0
        if not self.wait(self.port, 60):
            if self.connected():
                self.log('SKIP: Radeon monitor appeared while waiting')
                return 0
            if self.hardware_ready() != 'ready' or not self.discover_client():
                self.log('SKIP: controller removed before rebind')
                return 0
            name = self.client.name
            self.log(f'RECOVER: missing Type-C port; rebind UCSI client {name} once')
            self.write(self.driver / 'unbind', name)
            self.write(self.driver / 'bind', name)
            if not self.wait(self.port, 60):
                self.log('FAIL: UCSI port still missing after one rebind; stopping')
                return 1
        if self.wait(self.partner_or_done, 60) != 'partner':
            self.log('SKIP: partner absent, display connected or hardware removed; no reset')
            return 0
        if self.connected():
            self.log('SKIP: Radeon monitor appeared; no connector reset')
            return 0
        command = self.root / 'kernel/debug/usb/ucsi' / self.client.name / 'command'
        if not command.is_file():
            self.log('FAIL: UCSI debugfs command unavailable; stopping')
            return 1
        before = self.bridge_probe()
        if not self.known_bad_bridge(before):
            self.log('SKIP: known zero-sink bridge state not confirmed; no reset')
            return 0
        self.log('NEGOTIATE before=' + json.dumps(before, sort_keys=True))
        # Recheck immediately before the write; never reset an established display.
        if self.connected() or not self.dp_partner() or self.hardware_ready() != 'ready':
            self.log('SKIP: connection changed before renegotiation')
            return 0
        self.log(f'RECOVER: connector 1 reset on Radeon UCSI {self.client.name}, once')
        self.write(command, '0x10003')
        after = self.wait(self.renegotiated, 20)
        connector = self.connected()
        if not after or not connector:
            self.log('FAIL: bridge/display not confirmed after one renegotiation; stopping')
            return 1
        self.log('NEGOTIATE after=' + json.dumps(after, sort_keys=True))
        self.log(f'OK: {connector.name} connected; enabled={self.read(connector / "enabled")}')
        return 0


def bridge_sample(name):
    if not name.startswith('drm_dp_aux') or not name[10:].isdigit():
        raise ValueError('Invalid AUX name')
    gpu = Path('/sys/bus/pci/devices/0002:05:00.0')
    aux = Path('/sys/class/drm_dp_aux_dev') / name
    connector = (aux / 'device').resolve()
    if (not connector.is_relative_to(gpu.resolve()) or '-DP-' not in connector.name
            or Recovery.read(gpu / 'vendor') != '0x1002'
            or Recovery.read(gpu / 'device') != '0x73bf'):
        raise ValueError('Wrong AUX hardware')
    fd = os.open('/dev/' + name, os.O_RDONLY)
    try:
        def read(address, size):
            data = os.pread(fd, size, address)
            if len(data) != size:
                raise OSError('Short AUX read')
            return data
        identity = read(0x500, 9).hex()
        if identity != '00e04c4470312e3400':
            return {'identity': identity}
        return {'identity': identity, 'branch': bool(read(0x5, 1)[0] & 1),
                'ports': read(0x7, 1)[0] & 15, 'sinks': read(0x200, 1)[0] & 63,
                'power': read(0x600, 1)[0] & 7}
    finally:
        os.close(fd)


def main():
    if os.geteuid() != 0:
        raise SystemExit('Root is required')
    if len(sys.argv) == 3 and sys.argv[1] == '--bridge-sample':
        print(json.dumps(bridge_sample(sys.argv[2])))
        return 0
    kernel = os.uname().release
    if kernel not in {'7.3.3-m1-usb4-rc3'}:
        print(f'SKIP: kernel {kernel} is outside this rc3 candidate')
        return 0
    try:
        return Recovery().run()
    except (OSError, subprocess.SubprocessError) as exc:
        print(f'FAIL: {exc}; no further automatic attempt', flush=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
