# Probe42: Linux host-router queries before link activation

Preparation for OWC Express 1M2 at Mac port1, USB4 cable unchanged. Debug
connection stays at port0 beside Ethernet. This is a RAM-only U-Boot experiment,
not a kernel patch or an installed bootloader change.

## Evidence and hypothesis

Probe41 reached Phase2 but not Phase3 or Connected, with native USB host startup,
late PIPE setup and preserve-PHY DWC3 initialization already in place. All 61
control transactions returned. In the saved working Linux replug trace, Phase2
is followed by Phase3 in less than one millisecond and Connected shortly after.
These are host journal timestamps, not guaranteed firmware emission times.
Five seconds without progress in Probe41 argues against merely extending the wait.

The saved Linux failure near uptime 19 seconds is a loss of an already established
link, not an independent failed cold initialization. Do not treat it as a matched
cold-start control. Its fallback to native USB also does not prove a usable
host-side command to force USB3 before boot.

Linux's saved pre-cable trace includes root router operations omitted from the
prototype: NVM sector-size query 0x25, buffer allocation *parameter query* 0x33,
and DP-IN resource query 0x10 for ports 5 and 6. The opcode names do not mean that
flash is written or buffers allocated by this experiment. These are read-only
queries in Linux drivers/thunderbolt/usb4.c and tb_regs.h at the separately
audited source revision 517fe27a2ce7fa8d03aa6705a10ff4422197ff5d.
Linux copyright/authorship references remain in the source and this report;
no proprietary Apple source or disassembly is involved.

The hypothesis is only that completing these omitted router operations might
satisfy an undocumented firmware prerequisite. No source claims that they are
required for link training. A negative result closes this specific gap rather
than establishing a new PHY diagnosis.

## Exact delta and bounds

New explicit selector `atcm1 1 usb4query` retains Probe41's USB4/native-host guard.
After verified root configuration and inventory it queries NVM sector size once,
then buffer parameters, applies the existing TMU setup, then queries both DP-IN
resources. Inventory must identify exactly ports 5/6 as DP-IN before these calls.
Lane unlock and cable submission occur afterwards. This is not a byte-for-byte
Linux replay: redundant Linux NVM queries and its interleaving with inventory
are deliberately not copied.

Only route zero, port zero, router configuration space is used for the operations.
The write callback accepts only metadata values 0/5/6 at register 0x19 and the
three permitted opcode+OV values at 0x1a. There is no NVM write, authentication,
DP allocation, external tunnel or SSD operation. An already-busy operation
stops before any write. Completion is checked at most ten times, separated by
50 ms; the transport's existing per-message two-second and global ten-second
limits remain. This bounds the poll interval more tightly than Linux's 500 ms
wait. Unsupported operation reports are logged and skipped; other operation or
transport errors stop before link activation. Buffer response length cannot
exceed sixteen dwords.

NHI capacity grows from 64 to 128 entries without descriptor recycling. Its
allocation grows from four to six 16 KiB pages: TX/RX descriptor blocks each
one page, TX/RX packet blocks each two pages. Frame size stays 256 bytes;
DART page granularity stays 16 KiB. All allocations remain until mandatory reset.
Thus this is a comparison of the added query sequence plus required transport
capacity, not a strict single-variable analog timing experiment.

Validation: M1 build, 67 existing sandbox tests, 2,615 production-function query
cases with ASan/UBSan, 32,768 production callback allowlist cases, and all 512
DMA descriptor/packet extents checked for bounds and overlap. Transport failures
are injected at each query read/write and must stop further accesses.
Payload hashes and exact patch reconstruction are recorded before arming.

The existing internal NVMe before/after hash check and planned reset remain.
The configured 60-second watchdog and host runner are not a guarantee of recovery
from every hardware hang. Installed boot.bin, GRUB default and external SSD data
are unchanged. After the test, verify SSH, running kernel and original boot hash.
