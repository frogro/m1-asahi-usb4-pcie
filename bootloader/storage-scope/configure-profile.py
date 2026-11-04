#!/usr/bin/env python3
"""Set an explicit storage port/ESP in a COPY of a matching U-Boot control DTB."""
import argparse
from pathlib import Path
import subprocess
import tempfile
import uuid

def configure(source, output, port, partuuid):
    if port not in (0, 1):
        raise ValueError('M1 storage port must be 0 or 1')
    target = str(uuid.UUID(partuuid))
    source, output = Path(source), Path(output)
    if source.resolve() == output.resolve() or output.exists():
        raise ValueError('Use a new output file; the input is never modified')
    # Verify a control DTB with the existing integrated transport policy.
    value = subprocess.check_output(['fdtget', '-t', 's', str(source), '/config', 'bootcmd'], text=True).strip()
    if value not in ('tbboot', 'tbboot recovery'):
        raise ValueError('Input is not a supported integrated boot profile')
    with tempfile.TemporaryDirectory(dir=output.parent) as temporary:
        temp = Path(temporary) / 'profile.dtb'
        temp.write_bytes(source.read_bytes())
        for kind, name, value in [('s', 'bootcmd', 'tbboot'),
                                  ('x', 'u-boot,boot-port-mask', format(1 << port, 'x')),
                                  ('s', 'u-boot,boot-partuuid', target)]:
            subprocess.run(['fdtput', '-t', kind, str(temp), '/config', name, value], check=True)
        # Exclusive creation avoids accidentally overwriting another profile.
        with output.open('xb') as file:
            file.write(temp.read_bytes())

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--port', required=True, type=int, choices=(0, 1))
    parser.add_argument('--partuuid', required=True)
    args = parser.parse_args()
    configure(args.source, args.output, args.port, args.partuuid)
