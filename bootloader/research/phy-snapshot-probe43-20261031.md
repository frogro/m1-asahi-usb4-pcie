# Probe43: powered PHY state at the end of link observation

Probe42 answered all four additional host-router queries exactly like the saved
working Linux trace but again stopped at Phase2. The next comparison expands
the previous seventeen core/PIPE values to 61 reviewed core, PIPE and USB2
control/status registers, including PLL and lane controls.

The allowlist is derived from open-source Asahi Linux phy/apple/atc.c register
names and read/modify/write or status-poll usage. It excludes FIFOs, interrupts,
event banks and arbitrary address input. USB2 is at 0x502a90000, PIPE at
0x502a84000 and core at 0x503000000, checked against the existing U-Boot resource
validation. The saved Linux helper requires the exact corrected kernel,
a live OWC on NHI1 with both lanes active, and powered ACIO/PHY domains before
each read. It performs no MMIO writes and no disk I/O.

The U-Boot `usb4snapshot` selector otherwise follows Probe42. Its single-use
observer is invoked only after the bounded link attempt, while ACIO firmware,
PHY power and diagnostic rings are still present. The callback is consumed
before invocation and cleared when ACIO returns. Reading/printing occurs after
link polling, so it does not delay initial cable submission or change the five
second observation window. Firmware shutdown follows the snapshot. Existing
post-shutdown summaries remain distinguishable.

A training-failed snapshot and a connected Linux snapshot represent different
states. Differences may be consequences of training rather than missing setup.
They must be traced back to the source and register semantics before becoming
candidate writes. This measurement does not prove a PHY fix, a tunnel or boot.

M1 build, 67 sandbox tests, a production-function 61-read allowlist check,
observer-order/cleanup checks, unchanged M1 configuration and exact patch
reconstruction are required before arming. Internal NVMe hashes and planned
reset remain; the existing 60-second watchdog is not a recovery guarantee.
No installed bootloader change, external SSD write or new kernel installation.

## Complete source checkpoint

[The cumulative development patch](probe43-cumulative-source.patch) includes
all 46 modified/new source files over the pinned U-Boot base
b33034a515a068381c4aa28831fb709e91300cd1. It was applied to pristine copies of
the affected base files and every resulting file compared byte-for-byte with
the candidate checkout. The [manifest](../validation/probe43-cumulative-source-manifest.json)
records their hashes. This preserves the preceding probe work as well as the
new measurement; it remains an experimental diagnostic, not an installer release.

## Hardware result

Probe43 returned all 61 reviewed powered PHY/PIPE/USB2 values exactly equal to
the connected, two-lane Linux reference. All 81 NHI control transactions replied,
but both lanes remained in state 7 and firmware reported Phase2 only. No remote
router or external PCIe tunnel was reached. Internal NVMe hashes match. The
planned reset returned to stock Ubuntu with the original boot bundle unchanged.

This rules out a missing final value within this sampled set, not differences
in initialization order or transient states. The user also reported that the
OWC LED may have been off. Existing CD321x register 0x20 is SYSTEM_POWER_STATE,
not POWER_STATUS (0x3f), and neither is a physical voltage measurement. A
bounded read-only power-status comparison is the next diagnostic before new
PCIe-C initialization writes. No power fault or repair is claimed.
