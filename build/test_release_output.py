import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('release_output', Path(__file__).with_name('release-output.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class ReleaseOutputTests(unittest.TestCase):
    def test_missing_tag_and_draft_are_created_at_exact_commit(self):
        ref = {'object': {'type': 'commit', 'sha': 'a'*40}}
        release = {'id': 3, 'draft': True, 'tag_name': 'kernel-build-12-1'}
        with patch.object(m, 'gh', side_effect=[None, ref, None, [], release]) as gh:
            self.assertEqual(release, m.ensure_draft('owner/repo', 'kernel-build-12-1', 'a'*40))
            self.assertEqual({'ref': 'refs/tags/kernel-build-12-1', 'sha': 'a'*40}, gh.call_args_list[1].kwargs['payload'])
            self.assertTrue(gh.call_args_list[4].kwargs['payload']['draft'])

    def test_existing_draft_is_found_through_release_list(self):
        ref = {'object': {'type': 'commit', 'sha': 'a'*40}}
        release = {'id': 3, 'draft': True, 'tag_name': 'kernel-build-12-1'}
        with patch.object(m, 'gh', side_effect=[ref, None, [release]]) as gh:
            self.assertEqual(release, m.ensure_draft('owner/repo', 'kernel-build-12-1', 'a'*40))
            self.assertEqual(3, gh.call_count)

    def test_existing_wrong_tag_is_never_moved(self):
        with patch.object(m, 'gh', return_value={'object': {'type': 'commit', 'sha': 'b'*40}}) as gh:
            with self.assertRaisesRegex(RuntimeError, 'exact build commit'):
                m.ensure_draft('owner/repo', 'kernel-build-12-1', 'a'*40)
            self.assertEqual(1, gh.call_count)

    def test_published_release_is_not_modified(self):
        with patch.object(m, 'gh', side_effect=[{'object': {'type': 'commit', 'sha': 'a'*40}}, {'draft': False, 'tag_name': 'kernel-build-12-1'}]):
            with self.assertRaisesRegex(RuntimeError, 'published'):
                m.ensure_draft('owner/repo', 'kernel-build-12-1', 'a'*40)

    def test_permission_failure_is_not_treated_as_missing_release(self):
        result = subprocess.CompletedProcess([], 1, json.dumps({'status': '403'}), 'Forbidden')
        with patch.object(m.subprocess, 'run', return_value=result):
            with self.assertRaisesRegex(RuntimeError, 'Forbidden'):
                m.gh('api', 'anything', optional=True)

    def test_404_can_mean_no_existing_target(self):
        result = subprocess.CompletedProcess([], 1, json.dumps({'status': '404'}), 'Not Found')
        with patch.object(m.subprocess, 'run', return_value=result):
            self.assertIsNone(m.gh('api', 'anything', optional=True))

    def test_upload_retries_then_checks_server_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp)/'RUN.txt'; f.write_text('exact-build-identity')
            digest = m.hashlib.sha256(f.read_bytes()).hexdigest()
            asset = {'name': f.name, 'size': f.stat().st_size, 'state': 'uploaded', 'digest': 'sha256:'+digest}
            draft = {'draft': True, 'tag_name': 'kernel-build-12-1', 'assets': []}
            complete = dict(draft, assets=[asset])
            with patch.object(m, 'gh', side_effect=[draft, draft, RuntimeError('interrupted'), draft, None, complete]) as gh, patch.object(m.time, 'sleep'):
                m.upload('owner/repo', 'kernel-build-12-1', 3, [f])
                self.assertEqual(6, gh.call_count)
                self.assertEqual(gh.call_args_list[2], gh.call_args_list[4])
                self.assertIn('https://uploads.github.com/repos/owner/repo/releases/3/assets?name=RUN.txt', gh.call_args_list[4].args)

    def test_upload_digest_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp)/'RUN.txt'; f.write_text('exact-build-identity')
            draft = {'draft': True, 'tag_name': 'kernel-build-12-1', 'assets': []}
            bad = dict(draft, assets=[{'name': f.name, 'size': f.stat().st_size, 'state':'uploaded', 'digest':'sha256:wrong'}])
            with patch.object(m, 'gh', side_effect=[draft, draft, None, bad]):
                with self.assertRaisesRegex(RuntimeError, 'verification failed'):
                    m.upload('owner/repo', 'kernel-build-12-1', 3, [f])

    def test_changed_or_published_target_is_not_uploaded(self):
        for draft, tag in [(False, 'kernel-build-12-1'), (True, 'untagged-other')]:
            with self.subTest(draft=draft, tag=tag), patch.object(m, 'gh', return_value={'draft':draft,'tag_name':tag}) as gh:
                with self.assertRaisesRegex(RuntimeError, 'target changed'):
                    m.upload('owner/repo', 'kernel-build-12-1', 3, [Path('RUN.txt')])
                self.assertEqual(1, gh.call_count)

    def test_retry_replaces_incomplete_asset_only_on_reserved_draft(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp)/'a b.txt'; f.write_text('data')
            asset = {'id': 9, 'name': f.name, 'size': 4, 'state': 'uploaded', 'digest': 'sha256:'+m.hashlib.sha256(b'data').hexdigest()}
            draft = {'draft': True, 'tag_name': 'kernel-build-12-1', 'assets': [dict(asset, state='starter')]}
            complete = dict(draft, assets=[asset])
            with patch.object(m, 'gh', side_effect=[draft, draft, None, None, complete]) as gh:
                m.upload('owner/repo', 'kernel-build-12-1', 3, [f])
                self.assertEqual(('api','--method','DELETE','repos/owner/repo/releases/assets/9'), gh.call_args_list[2].args)
                self.assertIn('https://uploads.github.com/repos/owner/repo/releases/3/assets?name=a%20b.txt',gh.call_args_list[3].args)


if __name__ == '__main__':
    unittest.main()
