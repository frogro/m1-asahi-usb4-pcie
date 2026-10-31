# Probe36 result and Probe37 xHCI register-layout correction

Probe36 reports cap length 0x20, HCSPARAMS1 0x0200047f (two ports, four
interrupters, 127 slots), HCSPARAMS2 0x1c0000f1, runtime offset 0x440,
doorbell offset 0x4e0 and page-size bitmap 1. The old diagnostic erroneously
required runtime and doorbell offsets >= 0x1000. Its port-count check passed.
DWC3 core-init and USB-DART guards passed. The guard stopped before xHCI
allocation/reset/RUN, with 41/41 NHI control replies, Phase2 but no Phase3.
Internal NVMe hashes match, automatic reset returned stock Ubuntu and the
installed boot hash is unchanged; GRUB next_entry is empty.

The existing U-Boot xhci_mem_init uses capability-provided runtime and
doorbell offsets. xhci_hcor places port registers at operational +0x400;
port sets are 16 bytes, runtime header 32 bytes and interrupter sets 32 bytes,
doorbells four bytes per slot plus the host slot. On the measured hardware:
operational/ports end at 0x440, runtime spans 0x440..0x4df and doorbells
0x4e0..0x6df. These adjacent regions do not overlap.

Probe37 validates alignment, full region bounds and non-overlap in place of
the arbitrary 0x1000 minimum. The conservative 16-port/64-scratchpad limits
remain; interrupts must be 1..128 as supported by U-Boot's runtime array.
The original 0xa000 upper bound now applies to entire regions, not just
start offsets. No ordinary-driver behavior changes: this is hostrun only.
All retained-context, DART, no USB enumeration/SSD access, watchdog and
mandatory-reset restrictions from Probe35 remain. No installed changes.

Validation: M1 build, 48 extracted sanitizer cases including the exact
hardware tuple, adjacency, overlap, bounds, invalid interrupters and the
full mocked start path; four source contracts, exact one-file patch
reconstruction and unchanged build configuration. Prior sandbox tests were
not repeated for this focused guard change. Hardware outcome pending.
