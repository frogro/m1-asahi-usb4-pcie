# Probe31: compare DWC3 control state

Linux reference is a live boot of 7.2.12-usb4sd4-egpu2, not the stock kernel.
The initial capture had no USB4 router and is labelled linux-initial.json.
The accepted linux-usb4.json has Express 1M2, two lanes at 20 Gb/s each and
authorization 1. A second capture and kernel journal confirm NVMe enumeration.
The first replug watcher attempted authorization before its capture and got
EINVAL during connection setup. It produced no accepted register result. The
corrected watcher only reads state; capture succeeded after automatic binding.

The source reference is the separately identified Linux checkout from the
Phase2 audit, newer than the tested binary. Driver comments require core init,
Apple CIO settings, host mode, SUSPHY enabled and only then phy_set_mode.
This is distinct from enabling xHCI DMA; Probe31 does not enable xHCI.

Read 13 fixed controls and xHCI command/status at three points: before U-Boot
USB driver removal, after PHY/reset setup, and after ACIO diagnostic cleanup.
No FIFO, event-ring or device-mode reads; no additional MMIO writes. The USB
controller power domain remains held by the existing diagnostic. Probe31
reuses Probe30 sequence and payload reset, while instrumenting controller
state. More logging before ACIO may shift elapsed time; timing is not claimed
unchanged. Post-ACIO is after cleanup, not a snapshot during active training.

M1 build passed, patch reconstruction matched, extracted snapshot function
passed ASan/UBSan fixture checks for 45 allowed reads across three phases.
Hardware result follows below. No permanent bootloader installation.

## Hardware result and Probe32

Probe31 captured all three snapshots, internal NVMe hashes matched, reset
completed and stock Ubuntu returned. Firmware again stopped at Phase2.
GCTL changed from 0x30c11004 before removal to 0x30c12004 after reset: host
role became device role. Linux uses 0x30c11006 (host plus hibernation bit).
CIO LFPS/BW offsets were zero rather than Linux 0x0f800f80/0x0fc00fc0;
timer was 0x3c20060c rather than 0x3c140a10. USB3 SUSPHY was already set;
USB2 SUSPHY and ENBLSLPM were clear. This is a measured omitted controller
reinitialization, but its causal role in Phase2 is not yet established.

Probe32 tests the selected Apple CIO/host/PHY-suspend sequence as a unit.
It verifies the measured DWC3.1 core ID, DRD capability, no core reset and
xHCI halted. CIO controls are updated with readback; upper timer bits are
preserved. SUSPHY is cleared for role switching, role is set to HOST, then
USB2 ENBLSLPM and both SUSPHY bits are enabled before PIPE. xHCI must remain
halted. Any mismatch aborts the post-cable callback and existing cleanup
runs; there is no retry or OS handover without reset. Hibernation and
gadget-only GUCTL1 bits are deliberately not copied from the Linux snapshot.
This is not a full Linux DWC3 core port. 26 extracted-source mock cases
passed, including every one of 19 read-fault positions, bad core identity,
wrong stage, reset-active and halt-check failures. M1 build and exact patch
reconstruction passed. Probe32 hardware is pending.
