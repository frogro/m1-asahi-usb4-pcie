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
Hardware outcome pending.

A Linux DWC3 register capture on the connected TB3 device stopped at its core
ID guard (GSNPSID read 0). It is not a valid DWC3 reference and no subsequent
controls were read or written by that script. Power-domain active alone did
not establish accessible DWC3 core state. Do not infer a usable host from it.
