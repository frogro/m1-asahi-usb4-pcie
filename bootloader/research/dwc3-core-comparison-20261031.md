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
Hardware result pending. No permanent bootloader installation.
