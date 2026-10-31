# Probe37 outcome; Probe38 USB2 host-role comparison

Probe37 starts xHCI successfully: six DMA mappings, no mapping failure,
RUN=1, HALTED=0, both root ports powered with PORTSC=0x2a0. The later halt
also succeeds. Both USB DARTs retain verified bypass with no valid error;
the NHI DART reports no valid fault. All 61 NHI requests receive replies,
but both lanes remain state7 and firmware stays at Phase2. No remote router,
PCIe tunnel or SSD access. Internal NVMe hashes match; stock Ubuntu returns
automatically and the installed boot bundle remains unchanged.

This establishes the omitted host-start operation, not a solution to the
link stall. Full Linux DWC3 configuration equivalence is still not proven.

Source comparison found another omitted operation: dwc3_apple_init selects
the USB2 host role before DWC3 accesses the PHY; atcphy_usb2_set_mode sets
USB2PHY_SIG_HOST (7 << 12). The Linux comment specifically requires selecting
the role while USB2 is off, or the change may only take effect next time.
Our prototype performed USB2 power-off/on but never selected this role.
Source: Linux checkout 517fe27a2ce7fa8d03aa6705a10ff4422197ff5d,
drivers/usb/dwc3/dwc3-apple.c and drivers/phy/apple/atc.c. Original Linux
PHY/USB controller implementation credit: Sven Peter and contributors.

Probe38 sets only those three host-role bits via read/modify/write while
USB2 is off, before existing VBUS force/reset release/RUN operations. This
prototype only supports host USB4/TBT. Four read-only USB2 control registers
are logged after PHY initialization and after the ACIO run, while the power
domain remains held. This adds no device enumeration or storage IO.
The relationship of this omission to firmware Phase2 is a hypothesis; a
negative result must not be reported as a solved TB boot problem.

A new sandbox test exercises USB4/TBT, both orientations and three initial
signal values, verifies unrelated bits are retained, and checks role selection
between power-off and RUN. Existing every-operation fault injection covers
the added read/write. All other Probe37 DMA guards, retained allocations,
watchdog and mandatory reset remain. No installed changes.

The USB2 signal update logs its already-read old value and proposed new value;
this adds no extra MMIO read and shows whether host-role bits were inherited.

Validation completed: M1 and sandbox builds; all 64 sandbox tests, including
the 12 role scenarios; unchanged config and exact three-file reconstruction.
Hardware outcome pending.
