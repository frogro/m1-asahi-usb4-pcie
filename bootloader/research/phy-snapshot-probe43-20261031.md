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
