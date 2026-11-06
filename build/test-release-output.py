#!/usr/bin/env python3
"""Exercise preparation/final upload without mutating draft release metadata."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('release_output', Path(__file__).with_name('release-output.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class ReleaseUploadTest(unittest.TestCase):
    def test_both_phases_leave_metadata_untouched(self):
        env = {'GITHUB_REPOSITORY':'frogro/m1-asahi-usb4-pcie', 'GITHUB_SHA':'a'*40,
               'GITHUB_RUN_ID':'123', 'GITHUB_RUN_ATTEMPT':'1'}
        for phase in ['prepare', 'upload']:
            with self.subTest(phase=phase), tempfile.TemporaryDirectory() as temp:
                previous = os.getcwd()
                try:
                    os.chdir(temp)
                    with patch.dict(os.environ,env), patch('sys.argv',['release-output.py',phase]), \
                         patch.object(module,'ensure_draft',return_value={'id':1}), \
                         patch.object(module,'upload') as upload, \
                         patch.object(module,'gh',side_effect=AssertionError('Unexpected metadata request')), \
                         patch.object(module.subprocess,'run'):
                        module.main()
                        self.assertEqual(upload.call_count,1)
                        names = [p.name for p in upload.call_args.args[3]]
                        self.assertIn('RUN.txt',names)
                        if phase=='upload': self.assertIn('release-notes.txt',names)
                finally:
                    os.chdir(previous)

if __name__ == '__main__':
    unittest.main()
