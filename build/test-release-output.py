#!/usr/bin/env python3
"""Keep release metadata updates independent of tag/workflow permissions."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('release_output', Path(__file__).with_name('release-output.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ReleaseNotesTest(unittest.TestCase):
    def test_updates_only_body(self):
        with patch.object(module, 'gh', return_value={'draft': True, 'tag_name': 'test'}) as api:
            module.update_notes('owner/repo', 'test', 123, 'Build checked')
            self.assertEqual(api.call_args.kwargs, {'payload': {'body': 'Build checked'}})
            self.assertEqual(api.call_count, 2)

    def test_refuses_published_or_wrong_target(self):
        for target in [{'draft': False, 'tag_name': 'test'}, {'draft': True, 'tag_name': 'other'}]:
            with self.subTest(target=target), patch.object(module, 'gh', return_value=target) as api:
                with self.assertRaises(RuntimeError):
                    module.update_notes('owner/repo', 'test', 123, 'Build checked')
                self.assertEqual(api.call_count, 1)


if __name__ == '__main__':
    unittest.main()
