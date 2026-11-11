import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('recovery', Path(__file__).with_name('radeon-usbc-startup.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.writes = []
        self.fail_port = False
        self.fail_display = False
        self.r = module.Recovery(self.root, self.write, lambda check, seconds: check())
        self.put(self.r.gpu / 'vendor', '0x1002')
        self.put(self.r.gpu / 'device', '0x73bf')
        self.put(self.r.pci / 'vendor', '0x1002')
        self.put(self.r.pci / 'device', '0x73a4')
        self.connector = self.r.gpu / 'drm/card0/card0-DP-4'
        self.put(self.connector / 'status', 'disconnected')
        self.put(self.connector / 'enabled', 'disabled')
        self.bridge = {'identity': '00e04c4470312e3400', 'branch': True, 'ports': 0, 'sinks': 0, 'power': 2}
        self.r.bridge_probe = lambda: self.bridge
        self.client = self.r.pci / 'i2c-3/3-0008'
        self.client.mkdir(parents=True)
        self.r.driver.mkdir(parents=True)
        (self.r.driver / '3-0008').symlink_to(self.client)
        self.put(self.root / 'kernel/debug/usb/ucsi/3-0008/command', '')

    @staticmethod
    def put(path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def make_port(self, dp=True):
        port = self.client / 'typec/port2'
        port.mkdir(parents=True, exist_ok=True)
        if dp:
            self.put(port / 'port2-partner/port2-partner.0/svid', 'ff01')

    def write(self, path, value):
        self.writes.append((path.name, value))
        if path.name == 'bind' and not self.fail_port:
            self.make_port()
        if path.name == 'command' and not self.fail_display:
            self.put(self.connector / 'status', 'connected')
            self.bridge = {**self.bridge, 'ports': 1, 'sinks': 1, 'power': 1}

    def test_wrong_hardware_never_touched(self):
        self.put(self.r.pci / 'vendor', '0x1234')
        self.assertEqual(self.r.run(), 0)
        self.assertEqual(self.writes, [])

    def test_connected_monitor_not_touched_even_without_ucsi_port(self):
        self.put(self.connector / 'status', 'connected')
        self.assertEqual(self.r.run(), 0)
        self.assertEqual(self.writes, [])

    def test_other_controller_client_not_touched(self):
        (self.r.driver / '3-0008').unlink()
        other = self.root / 'devices/other-controller/3-0008'
        other.mkdir(parents=True)
        (self.r.driver / '3-0008').symlink_to(other)
        self.assertEqual(self.r.run(), 0)
        self.assertEqual(self.writes, [])

    def test_missing_display_partner_not_reset(self):
        self.make_port(dp=False)
        self.assertEqual(self.r.run(), 0)
        self.assertEqual(self.writes, [])

    def test_healthy_controller_gets_one_reset_only(self):
        self.make_port()
        self.assertEqual(self.r.run(), 0)
        self.assertEqual(self.writes, [('command', '0x10003')])
        self.assertEqual(self.r.run(), 0)
        self.assertEqual(len(self.writes), 1)

    def test_missing_port_rebinds_exact_client_then_resets(self):
        self.assertEqual(self.r.run(), 0)
        self.assertEqual(self.writes, [('unbind', '3-0008'), ('bind', '3-0008'), ('command', '0x10003')])

    def test_failed_port_recovery_stops_without_reset(self):
        self.fail_port = True
        self.assertEqual(self.r.run(), 1)
        self.assertEqual(self.writes, [('unbind', '3-0008'), ('bind', '3-0008')])

    def test_failed_reset_does_not_loop(self):
        self.make_port()
        self.fail_display = True
        self.assertEqual(self.r.run(), 1)
        self.assertEqual(self.writes, [('command', '0x10003')])


    def test_absent_gpu_stops_without_writes(self):
        import shutil
        shutil.rmtree(self.r.gpu)
        self.assertEqual(self.r.run(), 0)
        self.assertEqual(self.writes, [])

    def test_drm_not_registered_stops_without_reset(self):
        import shutil
        shutil.rmtree(self.r.gpu / 'drm')
        self.make_port()
        self.assertEqual(self.r.run(), 0)
        self.assertEqual(self.writes, [])

    def test_late_drm_registration_recovers_once(self):
        import shutil
        shutil.rmtree(self.r.gpu / 'drm')
        self.make_port()
        def wait(check, seconds):
            if check.__name__ == 'hardware_ready':
                self.assertIsNone(check())
                self.put(self.connector / 'status', 'disconnected')
            return check()
        self.r.wait = wait
        self.assertEqual(self.r.run(), 0)
        self.assertEqual(self.writes, [('command', '0x10003')])

    def test_unknown_bridge_not_reset(self):
        self.make_port()
        self.bridge['identity'] = '112233445566778899'
        self.assertEqual(self.r.run(), 0)
        self.assertEqual(self.writes, [])

    def test_unreadable_aux_not_reset(self):
        self.make_port()
        self.bridge = None
        self.assertEqual(self.r.run(), 0)
        self.assertEqual(self.writes, [])

    def test_positive_sink_without_drm_does_not_renegotiate(self):
        self.make_port()
        self.bridge['sinks'] = 1
        self.assertEqual(self.r.run(), 0)
        self.assertEqual(self.writes, [])

    def test_nonbranch_not_reset(self):
        self.make_port()
        self.bridge['branch'] = False
        self.assertEqual(self.r.run(), 0)
        self.assertEqual(self.writes, [])

    def test_monitor_appears_during_probe_not_reset(self):
        self.make_port()
        def probe():
            self.put(self.connector / 'status', 'connected')
            return self.bridge
        self.r.bridge_probe = probe
        self.assertEqual(self.r.run(), 0)
        self.assertEqual(self.writes, [])

    def test_drm_only_success_is_not_reported_as_bridge_recovery(self):
        self.make_port()
        def write(path, value):
            self.writes.append((path.name, value))
            self.put(self.connector / 'status', 'connected')
        self.r.write = write
        self.assertEqual(self.r.run(), 1)
        self.assertEqual(self.writes, [('command', '0x10003')])

    def test_partner_arriving_after_old_ten_second_window(self):
        self.make_port(dp=False)
        def wait(check, seconds):
            if check.__name__ == 'partner_or_done':
                self.assertGreaterEqual(seconds, 22)
                for second in range(23):
                    if second == 22:
                        self.make_port()
                    result = check()
                    if result:
                        return result
                return None
            return check()
        self.r.wait = wait
        self.assertEqual(self.r.run(), 0)
        self.assertEqual(self.writes, [('command', '0x10003')])

    def test_display_connects_while_waiting_for_partner(self):
        self.make_port(dp=False)
        def wait(check, seconds):
            if check.__name__ == 'partner_or_done':
                self.put(self.connector / 'status', 'connected')
            return check()
        self.r.wait = wait
        self.assertEqual(self.r.run(), 0)
        self.assertEqual(self.writes, [])

    def test_gpu_removed_while_waiting_for_partner(self):
        import shutil
        self.make_port(dp=False)
        def wait(check, seconds):
            if check.__name__ == 'partner_or_done':
                shutil.rmtree(self.r.gpu)
            return check()
        self.r.wait = wait
        self.assertEqual(self.r.run(), 0)
        self.assertEqual(self.writes, [])

    def test_controller_removed_before_rebind(self):
        import shutil
        def wait(check, seconds):
            if check.__name__ == 'port':
                shutil.rmtree(self.r.pci)
            return check()
        self.r.wait = wait
        self.assertEqual(self.r.run(), 0)
        self.assertEqual(self.writes, [])


if __name__ == '__main__':
    unittest.main()
