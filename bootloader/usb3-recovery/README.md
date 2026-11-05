# USB3 recovery in the automatic transport source

This development profile adds the recovered USB enumeration fixes to the
November 2 automatic transport/dock source. It does not impose the separate
storage-scope profile's fixed controller restriction. The normal PCIe and USB4
discovery code is retained. This is a build profile, not an installer or release.

The regular loader aborted at an xHCI Address Device transaction error for a
USB3 SSD behind the dock. The historical R7/R10 candidates had successfully
booted this path but were not promoted because subsequent Linux boots were
unreliable. A fresh comparison also isolated a second failure: a 36-byte SCSI
INQUIRY transfer completed after 750 ms, exceeding the diagnostic 500 ms limit.

Patch 14 adds command-completion identity validation, confirmed Disable Slot
cleanup, bounded addressing retries, one physical child-port reset, negotiated
SuperSpeedPlus Gen2x1 identification, a 50 ms reset recovery delay, and the
normal 5000 ms bulk completion deadline. It does not select devices by vendor
or product ID. Unsupported SSP encodings fail explicitly; arbitrary speed modes
are not claimed as tested. Patch 15 resets the retained xHCI controller at EFI
handoff and verifies the halted/reset state while retaining DMA buffers.

The patches apply after patches 1–13 of the recorded integration. Their hashes,
the configuration, and affected source hashes are pinned in `manifest.json`.

```sh
python3 bootloader/usb3-recovery/build.py /path/to/asahi-u-boot /new/output --jobs 4
```

The build reconstructs the source, runs actual-function recovery, descriptor,
port-reset, and handoff harnesses, then builds Apple M1 U-Boot. No Mac boot
files are installed. No Googlebook image, firmware, key, or user data is built
or uploaded. A reproducible rebuild's binary hash is distinct from the local
hardware-tested binary; source identity does not certify that new binary.

Initial hardware evidence on November 4: the integrated enumeration-only
candidate found both the USB3 WD/Fanxiang EFI and the SanDisk EFI behind the
Dynabook. The subsequent handoff candidate reached the Googlebook GUI and
`sys.boot_completed=1`; the selected super partition was on the WD's USB3
10 Gbit/s connection. Three 256 MiB direct reads and checksum comparisons
passed. The observed run lasted about 278 seconds before a controlled Android reboot
returned to macOS. Kernel capture showed no DART translation fault, xHCI Host
System Error, I/O error or panic; two PCIe tunnel-reset timeouts and a recovered
Linux USB address error remain. The 600-second timer was not exercised.
Repeat qualification and permanent installation remain pending. Normal boot
files were restored and checked. See `validation.json` for details.

This does not fix the separate downstream USB4-router header rejection. USB4
Fanxiang behind the dock, direct TB/USB4 regressions, both port orientations,
and eGPU coexistence are not newly certified by this USB3 test. Earlier
USB/DART handoff faults must not be dismissed merely because one GUI boot
succeeded. The default integrated CI/release profile is unchanged.

## Integration update — 5 November

This directory is now included in the runtime integration branch. The common-menu
profile has a complete pinned build recipe and CI checks; older hardware notes
above are historical stages, not the final combined result. See
`docs/runtime-integration-20261105.md` at the repository root for current status.
