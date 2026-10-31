#!/usr/bin/env python3
"""Summarize buffered host timestamps without claiming firmware event times."""
import argparse
import hashlib
import json
import re
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('log', type=Path)
p.add_argument('--linux-comparison', type=Path,
               default=Path(__file__).with_name('linux-prelink-comparison.json'))
a = p.parse_args()
raw = a.log.read_bytes()
s = raw.decode(errors='replace')
records = [{'ms': int(ms), 'delta': int(delta), 'event': event}
           for ms, delta, event in re.findall(
               r'BOOT-TIMING ms=(\d+) delta=(\d+) event=([^\s]+)', s)]
footer = re.findall(r'BOOT-TIMING count=(\d+) dropped=(\d+)', s)
if not records or len(footer) != 1 or len(records) != int(footer[0][0]):
    raise SystemExit('Incomplete or ambiguous timing capture')
if any(b['delta'] < a['delta'] for a, b in zip(records, records[1:])):
    raise SystemExit('Non-monotonic relative timing')
def interval(start, end):
    left = [r for r in records if r['event'] == start]
    right = [r for r in records if r['event'] == end]
    if len(left) != 1 or len(right) != 1:
        return None
    return right[0]['delta'] - left[0]['delta']
linux = json.loads(a.linux_comparison.read_text())
result = {
    'scope': 'Host action and message-consumption times, not firmware emission times',
    'log_sha256': hashlib.sha256(raw).hexdigest(),
    'records': records,
    'dropped': int(footer[0][1]),
    'milliseconds': {
        'phy_sequence': interval('phy-sequence-begin', 'phy-sequence-return'),
        'phy_return_to_m3_start': interval('phy-sequence-return', 'm3-start-write'),
        'm3_start_to_firmware_state_return': interval('m3-start-write', 'firmware-state-poll-return'),
        'firmware_state_to_rings': interval('firmware-state-poll-return', 'nhi-control-rings-started'),
        'rings_to_cable_submit': interval('nhi-control-rings-started', 'cable-info-submit'),
        'cable_submit_to_link_return': interval('cable-info-submit', 'link-observation-return'),
    },
    'linux_seconds_cable_write_to_first_remote_request':
        linux['linux_seconds_cable_write_to_first_remote_request'],
    'phase3_observed': 'Entering Phase 3' in s,
    'connected_observed': 'Entering Connected' in s,
    'remote_router_read_pass': 'NHI-REMOTE-READ PASS' in s,
    'reset_observed': 'resetting ...' in s,
}
print(json.dumps(result, indent=2))
