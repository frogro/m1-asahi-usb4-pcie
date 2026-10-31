# Probe33: Thunderbolt 3 comparison

The user substituted the Yottamaster TB3 enclosure for the OWC USB4 enclosure
on the same Mac port, leaving the debug port and HDMI unchanged. Stock Linux
7.2.0-1001-asahi-arm reports Intel Ash Creek, generation 3, two RX and TX lanes
at 20 Gb/s each, authorized 1. Its journal reaches Phase3/Connected. This is
a router/link reference, not an external NVMe boot or I/O result.

The pre-existing PHY code already selected TBT, but the control-plane cable
metadata deliberately accepted only USB4. Probe33 extends this missing path,
following Linux drivers/usb/typec/tipd/core.c and tps6598x.h plus
drivers/thunderbolt/apple.c in the identified local reference checkout.
Intel VID status (register 0x59, nine bytes) is read twice and must match;
data-status is also checked before/after. Device mode supplies the legacy
adapter bit. Speed, active/passive, link training and orientation come from
CD321x data status as in Linux. DROM validation is shared without weakening
CRC, bounds or lane-pair checks. Simultaneous USB4/TBT, absent cable, unknown
speed and invalid mode are rejected; output remains untouched on failure.
Cable readback checks bits 0..4, 9 and 10, including TBT/legacy flags.

The controller setup, PHY ordering, polling limits, DMA ring allocation and
cleanup are unchanged from Probe32. No external PCIe tunnel or SSD access.
The diagnostic only attempts a remote-router configuration read if the link
state allows it, then resets. No permanent bootloader install.

M1 and sandbox builds pass. 62 sandbox tests pass, including TB3 block-length,
transport-fault and changed-VDO checks. The extracted production transport
fixture passes 207 ASan/UBSan cases across USB4 and TBT, including 48 cable-flag
combinations and rejected metadata. Exact patch reconstruction passes.
Hardware Probe33 stops with -EPROTO in the CD321x snapshot before PHY setup.
The register/length is not yet instrumented, so this is not a TB3 link result.
Internal NVMe control hashes match and reset was observed. Ubuntu SSH return and the unchanged installed boot bundle are confirmed. No external SSD access occurred.

A source comparison identifies a candidate cause: the prototype requires an
exact register length prefix, while Linux tps6598x_block_read() accepts a
prefix at least as large as the requested fields. Capture the actual response
before changing validation; do not weaken checks based on this hypothesis alone.

A Linux DWC3 register capture on the connected TB3 device stopped at its core
ID guard (GSNPSID read 0). It is not a valid DWC3 reference and no subsequent
controls were read or written by that script. Power-domain active alone did
not establish accessible DWC3 core state. Do not infer a usable host from it.

Follow-up read-only Linux capture: Intel VID status (0x59) reports length 11,
with nine-byte payload prefix `030000000003000000`. Earlier identity/status
register lengths match. This confirms an input rejected by the prototype;
the exact failing U-Boot read was not logged. Probe34 accepts the measured
11-byte layout only for this register, retains nine-byte decoding and all
other bounds/stability checks, and logs any remaining length mismatch.

Probe34 preparation: M1 build and all 63 sandbox tests pass, including the
measured TB3 vector and every possible length byte at each Intel status read.
Changed data and invalid-length output preservation remain checked. The
isolated two-file delta reconstructs exactly; the U-Boot configuration is
unchanged. Hardware Probe34 now confirms the corrected TB3 status reader.


## Hardware comparison result

Probe34 accepts TB3 status and programs cable info 0x413 (TB3, present,
20-Gb/s cable, reversed orientation). PHY preflight, ACIO firmware startup,
DART/NHI setup, host inventory, lane unlock, DWC3 host setup and late PIPE
all succeed. All 61 control requests receive responses. The five-second
observation still sees only Phase2 and both lanes at state 7; there is no
Phase3/Connected message or external-router read. Final status is -ETIMEDOUT.
Internal NVMe control hashes match; mandatory reset is recorded.

This reproduces the earlier OWC USB4 stopping point with the Yottamaster TB3
path. It argues against an OWC-only or USB4-only explanation, but does not
prove a single common cause. The two runs also differ in physical cable and
orientation. The exact Phase2 cause remains open. Neither run establishes a
PCIe tunnel, external SSD I/O or external Thunderbolt boot.

Next source-level comparison should target shared host/PHY activation and
Linux ordering, including what is absent while xHCI remains halted. Starting
RUN on removed/freed xHCI rings is not a valid experiment; any full host-start
comparison needs proper controller registration and valid DMA ownership.

Ubuntu 7.2.0-1001-asahi-arm returned automatically and is reachable over SSH.
The installed boot bundle SHA-256 is unchanged and GRUB next_entry is empty.
The 61 transactions include repeated lane-status polls, not 61 boot stages.
After ten unsuccessful polling rounds the diagnostic returns -ETIMEDOUT;
it does not issue the external-router read while the link is unavailable.
