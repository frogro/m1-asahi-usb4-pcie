# SPDX-License-Identifier: MIT
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import install as core
import update


def fixture(number=200, version='7.2.12-usb4sd4-egpu3', attempt=1):
    tag=f'kernel-build-{number}-{attempt}'
    archive=dict(name='linux-'+version+'-arm64.tar.zst',sha256='a'*64,size=123)
    manifest=dict(schema=1,installer_contract=core.INSTALLER_CONTRACT,status='build-verified',
                  architecture='arm64',machine='apple,j274',profile='egpu',release=version,
                  kernel_base=core.KERNEL_BASE,build_commit='b'*40,run_id=number,run_attempt=attempt,archive=archive)
    def asset(name,size,digest):
        return dict(name=name,size=size,state='uploaded',digest=digest,
                    browser_download_url=core.REPO+'/releases/download/'+tag+'/'+name)
    release=dict(tag_name=tag,draft=False,prerelease=False,assets=[
        asset(archive['name'],123,'sha256:'+'a'*64),asset('installer-manifest.json',100,None)])
    run=dict(id=number,run_attempt=attempt,status='completed',conclusion='success',head_sha='b'*40,
             head_branch='main',event='workflow_dispatch',path='.github/workflows/consolidated-kernel.yml',
             head_repository=dict(full_name='frogro/m1-asahi-usb4-pcie'))
    return release,manifest,run


class ReleaseTests(unittest.TestCase):
    def test_complete_compatible_build(self):
        r,m,b=fixture()
        selected=core.validate_build(r,m,b)
        self.assertEqual(selected['tag'],r['tag_name'])
        self.assertEqual(selected['url'],r['assets'][0]['browser_download_url'])

    def test_running_failed_other_repo_or_attempt_rejected(self):
        r,m,b=fixture()
        changes=[dict(status='in_progress'),dict(conclusion='failure'),dict(head_sha='c'*40),
                 dict(head_branch='pull-request'),dict(run_attempt=2),dict(event='pull_request'),
                 dict(head_repository=dict(full_name='someone/else')),dict(path='other.yml')]
        for change in changes:
            with self.subTest(change=change),self.assertRaises(RuntimeError):
                core.validate_build(r,m,dict(b,**change))

    def test_wrong_machine_contract_payload_or_version_rejected(self):
        r,m,b=fixture()
        for change in [dict(machine='apple,j293'),dict(profile='storage'),dict(architecture='x86_64'),
                       dict(installer_contract='j274-egpu-v2'),dict(status='failed'),
                       dict(release='../escape'),dict(release='7.3.0-usb4sd4-egpu3'),dict(kernel_base='c'*40)]:
            with self.subTest(change=change),self.assertRaises(RuntimeError):
                core.validate_build(r,dict(m,**change),b)

    def test_draft_incomplete_or_mismatched_asset_rejected(self):
        r,m,b=fixture()
        with self.assertRaises(RuntimeError):core.validate_build(dict(r,draft=True),m,b)
        for change in [dict(digest='sha256:'+'c'*64),dict(size=99),dict(state='new'),
                       dict(browser_download_url='https://example.org/kernel')]:
            bad=copy.deepcopy(r);bad['assets'][0].update(change)
            with self.subTest(change=change),self.assertRaises(RuntimeError):core.validate_build(bad,m,b)

    def test_latest_orders_builds_not_listing_or_publication_order(self):
        older=fixture(199);new=fixture(200)
        def fetch(url):
            if '/releases?' in url:return [older[0],new[0]]
            if url.endswith('installer-manifest.json'):return new[1]
            return new[2]
        self.assertEqual(core.resolve_build(fetch=fetch)['run_id'],200)

    def test_pin_does_not_choose_newer(self):
        r,m,b=fixture(199)
        def fetch(url):
            if '/releases/tags/' in url:return r
            if url.endswith('.json'):return m
            return b
        self.assertEqual(core.resolve_build(r['tag_name'],fetch=fetch)['run_id'],199)

    def test_failed_newest_is_not_silently_replaced(self):
        r,m,b=fixture();b['conclusion']='failure'
        def fetch(url):
            if '/releases?' in url:return [r]
            if url.endswith('.json'):return m
            return b
        with self.assertRaises(RuntimeError):core.resolve_build(fetch=fetch)

    def test_no_release_or_network_error_never_uses_old_constant(self):
        with self.assertRaises(RuntimeError):core.resolve_build(fetch=lambda url:[])
        def offline(url):raise OSError('offline')
        with self.assertRaises(OSError):core.resolve_build(fetch=offline)

    def test_local_saved_state_no_network_and_ambiguity_guard(self):
        old_release=core.RELEASE;old_state=update.STATE
        try:
            with tempfile.TemporaryDirectory() as td,patch.object(update,'STATE_ROOT',Path(td)),patch.object(core,'resolve_build') as network:
                for v in ('7.2.12-usb4sd4-egpu2','7.2.12-usb4sd4-egpu3'):
                    d=Path(td)/v;d.mkdir();(d/'manifest.json').write_text(json.dumps(dict(release=v,target='internal-update')))
                with self.assertRaisesRegex(RuntimeError,'explicitly'):update.select_saved_state()
                update.select_saved_state('7.2.12-usb4sd4-egpu2')
                self.assertEqual(core.RELEASE,'7.2.12-usb4sd4-egpu2')
                self.assertEqual(update.STATE.name,core.RELEASE)
                network.assert_not_called()
                with self.assertRaises(RuntimeError):update.select_saved_state('../escape')
        finally:core.RELEASE=old_release;update.STATE=old_state

    def test_release_specific_grub_entries_preserve_legacy_rendering(self):
        m=dict(root_uuid='aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee',boot_uuid='11111111-2222-3333-4444-555555555555',
               internal_esp_uuid='ABCD-1234',release='7.2.12-usb4sd4-egpu2',model='APPLE SSD',target='internal-update')
        legacy=core.grub_entry(m)
        self.assertIn('sudo asahi-kernel-update --arm\'',legacy)
        self.assertNotIn('--release',legacy)
        new=core.grub_entry(dict(m,release='7.2.12-usb4sd4-egpu3',entry_id='asahi-update-test-egpu3',boot_manager_schema=2))
        self.assertIn('--id asahi-update-test-egpu3',new)
        self.assertIn('--release 7.2.12-usb4sd4-egpu3',new)
        with tempfile.NamedTemporaryFile(mode='w') as f:
            f.write(legacy+new);f.flush();subprocess.run(['grub-script-check',f.name],check=True)

    def test_boot_actions_never_resolve_latest(self):
        with patch('sys.argv',['update.py','--arm','--release','7.2.12-usb4sd4-egpu2']), \
             patch.object(core,'exclusive_operation'),patch.object(update,'select_saved_state') as saved, \
             patch.object(update,'arm') as arm,patch.object(core,'select_build') as latest:
            update.main();latest.assert_not_called();saved.assert_called_once_with('7.2.12-usb4sd4-egpu2',running=False);arm.assert_called_once()


if __name__=='__main__':unittest.main()

class HookTests(unittest.TestCase):
    def test_only_matching_kernel_gets_restore_hook(self):
        version='7.2.12-usb4sd4-egpu3'
        setup=update.dracut_setup(version,'usr/lib/asahi-kernel-update/'+version+'/boot-original.bin')
        subprocess.run(['bash','-n'],input=setup,text=True,check=True)
        for kernel,expected in [(version,0),('7.2.12-usb4sd4-egpu2',1),('7.2.0-stock',1)]:
            result=subprocess.run(['bash','-c',setup+'\nkernel="$1"; check','test',kernel])
            self.assertEqual(result.returncode,expected)
        self.assertIn('/'+version+'/boot-original.bin',setup)
