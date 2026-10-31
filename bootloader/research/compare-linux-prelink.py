#!/usr/bin/env python3
"""Compare saved Linux TB control traffic with Probe22; no hardware access."""
import argparse
import hashlib
import json
import re
from pathlib import Path


def compare(trace, probe):
    text = trace.read_text()
    log = probe.read_text()
    pattern = re.compile(
        r"\s(\d+\.\d+): tb_(tx|rx): type=(\w+),.*?route=(\d+), "
        r"offset=(0x[0-9a-f]+), len=(\d+), port=(\d+), "
        r"config=(0x[0-9a-f]+),.*?data=\[(.*?)\]"
    )
    packets = []
    for line in text.splitlines():
        match = pattern.search(line)
        if not match:
            continue
        stamp, direction, kind, route, offset, length, port, space, data = match.groups()
        words = [int(word.strip(), 16) for word in data.split(",")]
        packets.append(dict(time=float(stamp), direction=direction, kind=kind,
                            route=int(route), offset=int(offset, 16),
                            length=int(length), port=int(port), space=int(space, 16),
                            payload=words[3:]))
    remote = next(p for p in packets if p["direction"] == "tx" and p["route"] == 1)
    before = [p for p in packets if p["time"] < remote["time"]]
    headers = {}
    for match in re.finditer(r"NHI adapter port=(\d+) type=\w+ header=([0-9a-f ]+)", log):
        port = int(match[1])
        expected = [int(v, 16) for v in match[2].split()]
        observed = next(p for p in before if p["direction"] == "rx" and
                        p["kind"] == "TB_CFG_PKG_READ" and p["route"] == 0 and
                        p["space"] == 1 and p["port"] == port and
                        p["offset"] == 0 and p["length"] == 8)
        headers[port] = observed["payload"] == expected
    assert len(headers) == 7, "Incomplete adapter-header comparison"
    writes = [p for p in before if p["direction"] == "tx" and
              p["kind"] == "TB_CFG_PKG_WRITE" and p["route"] == 0]
    root = next(p for p in writes if p["space"] == 2 and p["offset"] == 1)
    unlocks = [p for p in writes if p["space"] == 1 and p["port"] in (1, 2)
               and p["offset"] == 4 and p["payload"] == [0x0ae00000]]
    cable = next(p for p in writes if p["space"] == 2 and p["offset"] == 0x36)
    expected_cable = int(re.search(r"NHI-CABLE-INFO PASS value=(0x[0-9a-f]+)", log)[1], 16)
    report = {
        "scope": "Saved traffic only; initial host writes compared with frozen Probe22 implementation/log",
        "inputs_sha256": {"linux_trace": hashlib.sha256(trace.read_bytes()).hexdigest(),
                          "probe22_log": hashlib.sha256(probe.read_bytes()).hexdigest()},
        "trace_buffer_header": next(line.strip() for line in text.splitlines()
                                    if "entries-in-buffer/entries-written" in line),
        "adapter_headers_match": headers,
        "root_configuration_matches_prototype": root["payload"] ==
            [0x1c71b, 0, 0x80000000, 0x200010ff],
        "both_lane_unlock_values_match": len(unlocks) == 2,
        "cable_info_matches": cable["payload"] == [expected_cable],
        "linux_seconds_cable_write_to_first_remote_request": round(remote["time"] - cable["time"], 6),
        "pre_remote_host_writes": writes,
        "interpretation": {
            "operations_25_33_10": "Source identifies NVM sector-size, buffer-allocation-parameter and DP-resource queries; not NVM writes or PCIe tunnel creation.",
            "adapter5_hotplug_write": "Linux writes 0xb016, already the value in Probe22's initial header; no demonstrated missing DHP clear in this capture.",
            "tmu": "Linux sets TD, sets 1000-interval LOWRES and clears TD at capability 0x1b; prototype omits this. Causality for physical link-up is unproven.",
            "post_link_write": "Port1 ADP_CS_4 becomes 0x4ae00000 after cable info; do not blindly replay this as a pre-link write.",
        },
    }
    assert all(headers.values())
    assert report["root_configuration_matches_prototype"]
    assert report["both_lane_unlock_values_match"]
    assert report["cable_info_matches"]
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("linux_trace", type=Path)
    parser.add_argument("probe22_log", type=Path)
    args = parser.parse_args()
    print(json.dumps(compare(args.linux_trace, args.probe22_log), indent=2))
