#!/usr/bin/env python3
"""Reserve the exact release target before compiling; upload only to that draft."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time


def gh(*args, payload=None, optional=False):
    command = ['gh', *args]
    if payload is not None:
        command += ['--input', '-']
    p = subprocess.run(command, input=json.dumps(payload) if payload is not None else None,
                       text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode:
        try:
            not_found = str(json.loads(p.stdout).get('status')) == '404'
        except (ValueError, AttributeError):
            not_found = False
        if optional and not_found:
            return None
        raise RuntimeError(p.stderr.strip() or p.stdout.strip() or 'GitHub command failed')
    return json.loads(p.stdout) if p.stdout.strip() else None


def ensure_draft(repo, tag, commit):
    prefix = 'repos/' + repo
    ref = gh('api', prefix + '/git/ref/tags/' + tag, optional=True)
    if ref is None:
        ref = gh('api', '--method', 'POST', prefix + '/git/refs',
                 payload={'ref': 'refs/tags/' + tag, 'sha': commit})
    if ref['object']['type'] != 'commit' or ref['object']['sha'] != commit:
        raise RuntimeError('Release tag does not point to the exact build commit')
    release = gh('api', prefix + '/releases/tags/' + tag, optional=True)
    if release is None:
        release = gh('api', '--method', 'POST', prefix + '/releases', payload={
            'tag_name': tag, 'target_commitish': commit, 'draft': True,
            'name': 'Kernel build ' + tag + ' (not installed)',
            'body': 'Build pending. Reserved upload target only; not an installable kernel.'})
    if not release['draft'] or release['tag_name'] != tag:
        raise RuntimeError('Refusing to modify a published or mismatched release')
    return release


def upload(repo, tag, paths):
    for path in paths:
        for attempt in range(3):
            try:
                gh('release', 'upload', tag, str(path), '--repo', repo, '--clobber')
                break
            except RuntimeError:
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)
    release = gh('api', 'repos/' + repo + '/releases/tags/' + tag)
    assets = {a['name']: a for a in release['assets']}
    for path in paths:
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        asset = assets.get(path.name, {})
        if (asset.get('size') != path.stat().st_size or
                asset.get('digest') != 'sha256:' + digest or
                asset.get('state') != 'uploaded'):
            raise RuntimeError('Uploaded asset verification failed: ' + path.name)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('phase', choices=['prepare', 'upload'])
    args = p.parse_args()
    repo, commit = os.environ['GITHUB_REPOSITORY'], os.environ['GITHUB_SHA']
    run, attempt = os.environ['GITHUB_RUN_ID'], os.environ['GITHUB_RUN_ATTEMPT']
    if repo != 'frogro/m1-asahi-usb4-pcie' or not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise RuntimeError('Unexpected build repository or commit')
    if not run.isdigit() or not attempt.isdigit():
        raise RuntimeError('Invalid run identity')
    tag = f'kernel-build-{run}-{attempt}'
    release = ensure_draft(repo, tag, commit)
    out = Path('artifacts')
    out.mkdir(exist_ok=True)
    record = out / 'RUN.txt'
    record.write_text(f'Build-only output. No deployment.\nRun: https://github.com/{repo}/actions/runs/{run}\nCommit: {commit}\n')
    if args.phase == 'prepare':
        upload(repo, tag, [record])
        print('Exact tag, draft creation and asset upload verified before compilation:', tag)
        return
    # RUN.txt is deterministic, so regenerating it does not invalidate sums.
    result = out / 'RESULT.txt'
    notes = out / 'release-notes.txt'
    notes.write_text((result.read_text() if result.is_file() else
                     'Build incomplete or failed. Diagnostics only.\n') + record.read_text())
    subprocess.run(['python3', 'build/prepare-assets.py'], check=True)
    gh('api', '--method', 'PATCH', 'repos/' + repo + '/releases/' + str(release['id']),
       payload={'body': notes.read_text()})
    upload(repo, tag, sorted(f for f in out.iterdir() if f.is_file() and f.stat().st_size))
    print('Draft assets uploaded and SHA-256 verified:', tag)


if __name__ == '__main__':
    main()
