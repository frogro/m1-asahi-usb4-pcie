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
            with patch.object(m, 'gh', side_effect=[RuntimeError('interrupted'), None, {'assets': [asset]}]) as gh, patch.object(m.time, 'sleep'):
                m.upload('owner/repo', 'kernel-build-12-1', 3, [f])
                self.assertEqual(3, gh.call_count)
                self.assertEqual(gh.call_args_list[0], gh.call_args_list[1])

    def test_upload_digest_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp)/'RUN.txt'; f.write_text('exact-build-identity')
            with patch.object(m, 'gh', side_effect=[None, {'assets': [{'name': f.name, 'size': f.stat().st_size, 'state':'uploaded', 'digest':'sha256:wrong'}]}]):
                with self.assertRaisesRegex(RuntimeError, 'verification failed'):
                    m.upload('owner/repo', 'kernel-build-12-1', 3, [f])


if __name__ == '__main__':
    unittest.main()
