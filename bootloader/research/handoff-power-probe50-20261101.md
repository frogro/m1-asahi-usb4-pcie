# Probe50: power state before and after U-Boot USB initialization

The question was whether normal U-Boot USB startup destroys an inherited
Thunderbolt connection before the explicit diagnostic starts. This probe
observes power state only; it cannot directly inspect an inherited tunnel.
It runs after m1n1's reported PMGR cleanup, not at the raw iBoot handoff.

The diagnostic build sets CONFIG_PREBOOT="" and
CONFIG_ENV_SOURCE_FILE="probe50". Its input/output/error consoles are serial
only, avoiding USB keyboard startup. The frozen boot command reads the 14
fixed J274 PMGR registers, hashes the internal control file, explicitly runs
`usb start`, repeats the PMGR reads and internal hash, then resets.

All board, parent resources and child offsets are validated before any MMIO.
The observation command does not probe devices, write MMIO, or access PHY,
ACIO, NHI or PCIe controller registers, even if their power state is active.
Normal explicit USB startup still initializes controllers and enumerates
USB devices. No external sector-read/write command is issued.

## Validation and observed result

The M1 build and 42 host cases using the production command body with real
libfdt passed under ASan/UBSan. Invalid board/resource/child data must fail
before the first read. These are software checks, not proof of hardware safety.

The UART confirms serial-only consoles and exactly one USB startup, after
the first snapshot. Both internal control hashes matched. USB initialization
succeeded but found no USB storage. Both 14-register snapshots completed.

Port1 PCIe (0x450), CIO (0x458), CIO-PCIe (0x460) and CIO-USB (0x468)
were powered down both before and after USB startup. Target/actual power,
reset and disable fields were unchanged for all 14 sampled registers.
Only historical gating flags cleared: 0x300 at PMGR 0x23b700448 and 0x200
at 0x23d280090 and 0x23d2800a0. Interpret these using apple-pmgr.c;
they do not represent power transitions observed during this test.

There was therefore no powered inherited CIO/PCIe path at this observation
point for USB startup to switch off. This does not show what raw iBoot leaves,
or what happens when booting an actual external macOS installation. The
internal Sonoma Test helper is not such an external macOS startup.

No new link training was attempted and no external router/SSD boot was proven.
Do not repeat this unchanged probe. Earlier handoff evidence and transient
link-training events remain the useful comparison targets. Recovery status
is recorded separately in m1-probe50-result.json.
