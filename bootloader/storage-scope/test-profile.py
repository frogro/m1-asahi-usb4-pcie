import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('profile', Path(__file__).with_name('configure-profile.py'))
profile = importlib.util.module_from_spec(spec)
spec.loader.exec_module(profile)

class ProfileTests(unittest.TestCase):
    def test_explicit_ports_preserve_hardware_and_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            src = root / 'in.dtb'
            subprocess.run(['dtc', '-I', 'dts', '-O', 'dtb', '-o', str(src)],
                input=b'/dts-v1/; / { config { bootcmd = "tbboot recovery"; }; hardware { sentinel = <0x1234>; }; };', check=True)
            before = src.read_bytes()
            for port in (0, 1):
                out = root / f'out{port}.dtb'
                profile.configure(src, out, port, '11111111-2222-3333-4444-555555555555')
                def get(node, prop, kind='s'):
                    return subprocess.check_output(['fdtget','-t',kind,str(out),node,prop],text=True).strip()
                self.assertEqual(get('/config','bootcmd'),'tbboot')
                self.assertEqual(get('/config','u-boot,boot-port-mask','x'),str(1 << port))
                self.assertEqual(get('/hardware','sentinel','x'),'1234')
                self.assertEqual(src.read_bytes(),before)
            for port, target in [(2,'11111111-2222-3333-4444-555555555555'),(0,'invalid')]:
                with self.assertRaises(ValueError): profile.configure(src,root/'bad.dtb',port,target)
                self.assertFalse((root/'bad.dtb').exists())
            with self.assertRaises(ValueError): profile.configure(src,src,0,'11111111-2222-3333-4444-555555555555')

if __name__ == '__main__': unittest.main()
