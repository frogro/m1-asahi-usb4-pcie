# Probe38 outcome and Probe39 preserve-PHY comparison

Probe38 changed USB2 SIG from 0x01c1000f to 0x01c1700f: host-role bits
0x6000 were missing. After the run SIG was 0x0041700f, with host bits still
set. xHCI starts/stops successfully, six DMA mappings, 61/61 NHI responses,
but both lanes remain state7 and ACIO remains in Phase2. No remote router or
external SSD access. Internal hashes match; stock Ubuntu returns automatically,
installed boot bundle unchanged and GRUB next_entry empty.

The next source comparison distinguishes two similarly named functions:
U-Boot drivers/usb/host/xhci-dwc3.c dwc3_core_init unconditionally calls
its legacy dwc3_core_soft_reset, asserting GCTL.CORESOFTRESET plus USB2 and
USB3 PHYSOFTRST and waiting 200 ms. Our late host hook invoked this after
submitting cable information and starting ACIO firmware lane training.
Linux drivers/usb/dwc3/core.c dwc3_core_soft_reset instead resets the device
side via DCTL (or returns immediately in host role); it does not perform
those PHY reset writes. This is a source-level difference, not proof of the
cause of the Phase2 stall.

Probe39 separates the existing U-Boot helper into a shared implementation
with a reset selector. The ordinary public dwc3_core_init still selects
reset=true. Only the explicit M1 RAM diagnostic calls the new preserve-PHY
entry point, after the existing ATC_CORE_READY, HALTED, controller-ID and
USB-DART guards. The earlier full ATC/DWC3 reset/release is retained, as are
all existing GCTL settings, CIO settings, SUSPHY/PIPE ordering, the subsequent
normal xHCI reset/start, port power, DMA guards, cleanup halt and full reset.
No device-mode DCTL reset is added; this is a host-only experiment, not a
claim of full Linux core-init equivalence.

Test fixture executes extracted old/new production functions with mocked
registers: 60 combinations of controller ID, power capability and initial
GCTL compare normal-path register writes/delays byte-for-byte, and verify the
diagnostic path gives identical final GCTL with no PHY writes or delays.
ASan/UBSan uses kernel-style -fno-strict-overflow, needed by existing upstream
signed 1<<31 register macros. The final run has empty sanitizer stderr.
Another 30 extracted host-setup cases retain halt/DART/failure ordering.
M1 build, unchanged config and exact patch reconstruction are prerequisites.
The earlier 64 sandbox tests are not repeated for this isolated helper change.

Original U-Boot xhci-dwc3 implementation credit: Ramneek Mehresh,
Freescale Semiconductor and contributors; existing source headers retained.
Linux reference: 517fe27a2ce7fa8d03aa6705a10ff4422197ff5d.
No permanent installation, external PCIe tunnel, USB enumeration or SSD IO.
Hardware outcome pending; the removed 200 ms delay is part of the reset
sequence, so this experiment also changes elapsed time before PIPE/xHCI.
