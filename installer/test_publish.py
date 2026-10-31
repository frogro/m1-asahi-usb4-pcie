# SPDX-License-Identifier: MIT
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from test_releases import fixture

spec=importlib.util.spec_from_file_location('publisher',Path(__file__).parents[1]/'build/publish-installer.py')
pub=importlib.util.module_from_spec(spec);spec.loader.exec_module(pub)


class PublishTests(unittest.TestCase):
    def test_unpublished_draft_can_be_verified_before_publication(self):
        release = dict(tag_name='kernel-build-12-1', draft=True, id=3)
        with patch.object(pub, 'api', return_value=[release]):
            self.assertEqual(pub.find_release('kernel-build-12-1'), release)

    def test_missing_release_is_not_replaced_by_another_build(self):
        with patch.object(pub, 'api', return_value=[dict(tag_name='kernel-build-11-1')]):
            with self.assertRaisesRegex(RuntimeError, 'not found'):
                pub.find_release('kernel-build-12-1')

    def create(self, td):
        d=Path(td);r,m,run=fixture();v=m['release'];archive=m['archive']['name']
        stage=d/'stage';stage.mkdir()
        for name in [f'boot/Image-{v}',f'boot/config-{v}',f'boot/dtbs/{v}/apple/t8103-j274.dtb',
                     f'lib/modules/{v}/modules.dep',f'lib/modules/{v}/kernel/amdgpu.ko.zst',
                     'usr/lib/firmware/apple/avd-fw-v2-t0.bin']:
            p=stage/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'test fixture')
        subprocess.run(['tar','--zstd','-cf',d/archive,'-C',stage,'.'],check=True)
        (d/'RESULT.txt').write_text('Build and module checks passed. Not installed. Hardware validation pending.\n')
        (d/'config-comparison.json').write_text(json.dumps(dict(result='passed',unexpected_changes={})))
        (d/'kernel-release.txt').write_text(v+'\n');(d/'RUN.txt').write_text('Commit: '+run['head_sha']+'\n')
        self.sums(d)
        a=d/archive;r['assets'][0].update(size=a.stat().st_size,digest='sha256:'+hashlib.sha256(a.read_bytes()).hexdigest())
        return d,r,run

    def sums(self,d):
        (d/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n'
                                         for p in d.iterdir() if p.is_file() and p.name!='SHA256SUMS'))

    def test_successful_payload(self):
        with tempfile.TemporaryDirectory() as td:
            d,r,run=self.create(td);m=pub.build_manifest(run,r,d)
            self.assertEqual(m['status'],'build-verified');self.assertEqual(m['run_id'],run['id'])

    def test_failed_workflow_or_report_never_promoted(self):
        with tempfile.TemporaryDirectory() as td:
            d,r,run=self.create(td)
            for field,value in [('conclusion','failure'),('head_branch','feature'),('event','pull_request')]:
                with self.assertRaises(RuntimeError):pub.build_manifest(dict(run,**{field:value}),r,d)
            (d/'RESULT.txt').write_text('failed');self.sums(d)
            with self.assertRaises(RuntimeError):pub.build_manifest(run,r,d)

    def test_archive_corruption_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            d,r,run=self.create(td)
            with (d/r['assets'][0]['name']).open('ab') as f:f.write(b'corrupt')
            with self.assertRaises(RuntimeError):pub.build_manifest(run,r,d)

    def test_incomplete_archive_even_with_matching_checksums(self):
        with tempfile.TemporaryDirectory() as td:
            d,r,run=self.create(td);name=r['assets'][0]['name']
            (d/'stage/usr/lib/firmware/apple/avd-fw-v2-t0.bin').unlink()
            subprocess.run(['tar','--zstd','-cf',d/name,'-C',d/'stage','.'],check=True)
            self.sums(d);data=(d/name).read_bytes();r['assets'][0].update(size=len(data),digest='sha256:'+hashlib.sha256(data).hexdigest())
            with self.assertRaisesRegex(RuntimeError,'Incomplete'):pub.build_manifest(run,r,d)
