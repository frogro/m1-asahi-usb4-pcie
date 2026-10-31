# SPDX-License-Identifier: MIT
import copy
import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
spec = importlib.util.spec_from_file_location('installer', Path(__file__).with_name('install.py'))
i = importlib.util.module_from_spec(spec)
spec.loader.exec_module(i)

class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.disk = dict(path='/dev/fake-test-usb', type='disk', tran='usb', size=250* i.GIB,
                         model='MP400', serial='test-serial', ro=False, mountpoints=[None],
                         children=[dict(path='/dev/fake-test-usb1', type='part', mountpoints=[None])])
        self.manifest = dict(boot_uuid='11111111-2222-3333-4444-555555555555',
                             root_uuid='aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee',
                             internal_esp_uuid='1234-ABCD', release=i.RELEASE, model='MP400')

    def test_mounted_root_and_children_rejected(self):
        self.assertEqual(i.disk_reasons(self.disk), [])
        for mount in ['/', '/boot', '/boot/efi', '/mnt/data', '[SWAP]']:
            d = copy.deepcopy(self.disk)
            d['children'][0]['mountpoints'] = [mount]
            self.assertTrue(i.disk_reasons(d))

    def test_non_usb_ro_small_missing_serial_rejected(self):
        for key, value in [('tran','nvme'),('tran','sata'),('type','loop'),('ro',True),
                           ('size',16*i.GIB),('serial','')]:
            d = dict(self.disk, **{key:value})
            self.assertTrue(i.disk_reasons(d), (key,value))

    def test_dm_child_rejected(self):
        self.disk['children'][0]['type'] = 'crypt'
        self.assertTrue(i.disk_reasons(self.disk))

    def test_identity_change_aborts(self):
        for key in ['serial', 'maj:min', 'size', 'model']:
            with patch.object(i, 'disks', return_value=[dict(self.disk, **{key:'different'})]):
                with self.assertRaises(RuntimeError): i.recheck_disk(self.disk)

    def test_grub_exact_pair_and_resource_arguments(self):
        entry = i.grub_entry(self.manifest)
        self.assertIn('root=UUID=' + self.manifest['root_uuid'],entry)
        self.assertIn('--set=externalboot ' + self.manifest['boot_uuid'],entry)
        self.assertIn('/Image-' + i.RELEASE,entry)
        self.assertIn('/initrd.img-' + i.RELEASE,entry)
        self.assertEqual(entry.count('pci=hpbussize='),1)
        for arg in ['hpmmioprefsize=512M','realloc=on','amdgpu.rebar=0','appledrm.hdmi_audio=1']:
            self.assertIn(arg,entry)
        with tempfile.NamedTemporaryFile(mode='w') as f:
            f.write(entry); f.flush()
            subprocess.run(['grub-script-check',f.name],check=True)

    def test_model_cannot_inject_grub(self):
        self.manifest['model'] = "MP400'\n}; reboot; #$foo"
        entry = i.grub_entry(self.manifest)
        self.assertNotIn("\n};",entry)
        self.assertNotIn('; reboot;',entry)
        self.assertIn('MP400',entry)

    def test_uuid_or_release_injection_rejected(self):
        for key in ['root_uuid', 'boot_uuid', 'internal_esp_uuid', 'release']:
            with self.assertRaises(RuntimeError):
                i.grub_entry(dict(self.manifest, **{key:'1234; reboot'}))

    def test_only_plan_default_no_writes(self):
        with patch('sys.argv', ['install.py']), patch.object(i,'select_build'), patch.object(i,'install') as install:
            i.main()
            install.assert_not_called()

    def test_dtb_replacement_preserves_everything_else(self):
        with tempfile.TemporaryDirectory() as td:
            td=Path(td)
            def dtb(compat,label):
                p=td/(label+'.dts'); out=td/(label+'.dtb')
                p.write_text('/dts-v1/; / { compatible="'+compat+'"; test="'+label+'"; };')
                subprocess.run(['dtc','-I','dts','-O','dtb','-o',out,p],check=True)
                return out.read_bytes()
            old=dtb('apple,j274','old'); new=dtb('apple,j274','new-longer')
            other=dtb('apple,j293','other')
            prefix=b'm1n1-and-uboot'+other
            suffix=b'end-of-bundle'
            self.assertEqual(i.replace_dtb(prefix+old+suffix,new),prefix+new+suffix)
            for bundle in [prefix+suffix,prefix+old+old+suffix]:
                with self.assertRaises(RuntimeError): i.replace_dtb(bundle,new)
            with self.assertRaises(RuntimeError): i.replace_dtb(prefix+old,other)

    def test_kernel_extraction_preserves_usr_merge(self):
        with tempfile.TemporaryDirectory() as td:
            td=Path(td); source=td/'source';target=td/'target'
            (source/'lib/modules/example').mkdir(parents=True)
            (source/'lib/modules/example/test.ko').write_bytes(b'module')
            (target/'usr/lib/firmware').mkdir(parents=True)
            (target/'lib').symlink_to('usr/lib')
            archive=td/'kernel.tar'
            subprocess.run(['tar','-cf',archive,'-C',source,'.'],check=True)
            subprocess.run(['tar','-xf',archive,'-C',target,'--keep-directory-symlink'],check=True)
            self.assertTrue((target/'lib').is_symlink())
            self.assertTrue((target/'usr/lib/modules/example/test.ko').is_file())
            self.assertTrue((target/'lib/firmware').is_dir())

    def test_initramfs_accepts_builtins_but_requires_usb_modules(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/'lib/firmware/apple').mkdir(parents=True)
            (root/'lib/firmware/apple/avd-fw-v3-t0.bin').write_bytes(b'firmware')
            def fake_output(*args):
                if args[0]=='lsinitrd': return i.RELEASE+' restore.sh boot-original.bin uas.ko.zst usb-storage.ko.zst'
                if 'vermagic' in args: return i.RELEASE+' SMP'
                return {'uas':'/lib/modules/uas.ko.zst', 'usb_storage':'/lib/modules/usb-storage.ko.zst'}.get(args[-1],'(builtin)')
            with patch.object(i,'output',side_effect=fake_output):
                i.verify_initramfs(root,root/'boot')
            def missing_output(*args):
                if args[0]=='lsinitrd': return i.RELEASE+' restore.sh boot-original.bin'
                return fake_output(*args)
            with patch.object(i,'output',side_effect=missing_output):
                with self.assertRaises(RuntimeError): i.verify_initramfs(root,root/'boot')
            def btrfs_output(*args):
                if args[0]=='modinfo' and args[-1]=='btrfs':return '/lib/modules/btrfs.ko.zst'
                return fake_output(*args)
            with patch.object(i,'output',side_effect=btrfs_output):
                with self.assertRaises(RuntimeError):
                    i.verify_initramfs(root,root/'boot',extra_modules=('btrfs',))
            def complete_btrfs_output(*args):
                if args[0]=='lsinitrd':return fake_output(*args)+' btrfs.ko.zst'
                return btrfs_output(*args)
            with patch.object(i,'output',side_effect=complete_btrfs_output):
                i.verify_initramfs(root,root/'boot',extra_modules=('btrfs',))

    def test_failed_download_not_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'file';p.write_bytes(b'incorrect')
            with self.assertRaises(RuntimeError): i.download('https://example.org', '0'*64,p)

    def test_restore_checks_both_hashes_and_marker(self):
        m=dict(self.manifest, original_sha='a'*64,candidate_sha='b'*64)
        s=i.restore_hook(m)
        self.assertIn('external-'+m['root_uuid']+'.armed',s)
        self.assertIn('"$current" = '+'b'*64,s)
        self.assertIn('"$saved" = '+'a'*64,s)
        with tempfile.NamedTemporaryFile(mode='w') as f:
            f.write(s);f.flush();subprocess.run(['sh','-n',f.name],check=True)

if __name__ == '__main__': unittest.main()
