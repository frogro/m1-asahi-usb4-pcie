# SPDX-License-Identifier: MIT
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parent))
import install as core
import update

class UpdateTests(unittest.TestCase):
    def test_newer_kernel_guard_and_custom_suffixes(self):
        values=['6.12.8','7.2.12-other-build','7.2.13-generic','7.3.0-asahi','7.10.0']
        self.assertEqual(update.newer_releases(values),values[2:])
        self.assertEqual(update.kernel_version('7.2.12-usb4sd4-egpu2'),(7,2,12))
        self.assertEqual(update.kernel_version('7.3'),(7,3,0))
        with self.assertRaises(RuntimeError):update.kernel_version('unknown')

    def test_distro_specific_grub_commands(self):
        self.assertEqual(update.commands('ubuntu')['rebuild'],['update-grub'])
        self.assertEqual(update.commands('fedora')['cfg'],'/boot/grub2/grub.cfg')
        with self.assertRaises(RuntimeError):update.commands('unrecognised')

    def test_fedora_selinux_and_subvolume_arguments(self):
        fedora=core.boot_options(dict(os_id='fedora',root_subvolume='/root'))
        self.assertIn('lsm=landlock,lockdown,yama,integrity,selinux,bpf',fedora)
        self.assertIn('rootflags=subvol=root',fedora)
        ubuntu=core.boot_options(dict(os_id='ubuntu'))
        self.assertNotIn('lsm=',ubuntu)
        self.assertNotIn('rootflags=',ubuntu)
        with self.assertRaises(RuntimeError):core.boot_options(dict(root_subvolume='/root; reboot'))

    def test_plan_does_not_prepare(self):
        with patch('sys.argv',['update.py']),patch.object(update,'plan') as plan,patch.object(update,'prepare') as prepare:
            update.main();plan.assert_called_once();prepare.assert_not_called()

    def test_existing_file_rollback_preserves_content(self):
        import tempfile
        # Exercise backup handling entirely inside an isolated temporary directory.
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); state=root/'state';dest=root/'config'
            dest.write_text('user configuration')
            changed=[]
            with patch.object(update,'STATE',state):
                update.save_and_write('config','new vendor content',changed,root=root)
                self.assertEqual(dest.read_text(),'new vendor content')
                update.restore_changed(changed,root=root)
                self.assertEqual(dest.read_text(),'user configuration')

    def test_backup_path_cannot_escape(self):
        for value in ('/etc/passwd', '../config', 'boot/../../config', ''):
            with self.assertRaises(RuntimeError):update.relative_path(value)

    def test_older_build_rejected_before_any_write(self):
        with patch.object(update,'context',return_value={}),patch.object(update,'preflight'), \
             patch.object(update,'installed_releases',return_value=['7.3.0-newer']), \
             patch.object(core,'json_write') as write:
            with self.assertRaisesRegex(RuntimeError,'Newer kernel'):
                update.prepare()
            write.assert_not_called()

    def test_exact_release_not_overwritten_even_with_override(self):
        with patch.object(update,'context',return_value={}),patch.object(update,'preflight'), \
             patch.object(update,'installed_releases',return_value=[core.RELEASE]), \
             patch.object(core,'json_write') as write:
            with self.assertRaisesRegex(RuntimeError,'Exact release'):
                update.prepare(allow_older=True)
            write.assert_not_called()

    def test_existing_default_and_menu_order_preserved(self):
        before='set default="0"\nmenuentry "old" {}\nsubmenu "advanced" {}\n'
        entry='menuentry "candidate" {}\n'
        update.verify_preserved_boot_selection(before,before+entry,entry)
        for after in (entry+before,(before+entry).replace('default="0"','default="1"')):
            with self.assertRaises(RuntimeError):
                update.verify_preserved_boot_selection(before,after,entry)

if __name__=='__main__':unittest.main()
