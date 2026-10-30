Automatic retained-power USB4 suspend follow-up, 2026-10-30

Apply these three patches after the existing 26-patch usb4sd2 series.
../series-with-suspend lists the complete 29-patch candidate. The previous
series and built kernel are preserved. No full-kernel installation or GitHub
workflow dispatch is performed by this follow-up.

The PHY retains its own domain in USB4/Thunderbolt mode. Each live ACIO
instance retains its attached domain list and releases retention on startup
failure or completed shutdown. Normal NHI suspend/resume stops and restarts
control DMA around DART PM. No address-based global retention module or
user-selectable diagnostic suspend mode is required. Full controller
power-loss recovery is not implemented; active-link hibernation/deeper
suspend is rejected explicitly.

Validation:
- Affected objects compiled against the reconstructed consolidated source.
- Matched diagnostic modules built with BTF and were used for hardware tests.
- Test154 late/noirq rehearsal passed; original UART loaded normally at boot.
- Test155 actual s2idle 34.342s: power-button wake, HDMI, and all hashes passed.
- Test156 orderly ACIO shutdown/start: PCIe power-off counter incremented;
  SSD re-enumerated and all hashes passed. PHY remains active during this
  software cycle because the Type-C cable has not been disconnected.
- Test157 actual s2idle 71.675s with asynchronous device PM enabled, after
  the controller cycle: HDMI and all hashes passed.

Read checks each time: Yottamaster Samsung 1GiB, OWC USB/UAS 1GiB, SD64MiB.
All media were verified unmounted and set read-only before direct reads.
No UART/watchdog/eGPU/TTM/NVMe-driver or ACK-classification patch is included.
Existing DCP PMU diagnostic persists without a demonstrated HDMI failure.

The live Apple test module backports the same retention/PM functions onto
the previous matched Test149 source to preserve the known diagnostic ABI.
It is not identical to the full consolidated Apple module; consequently a
combined-kernel boot is still required. Dock-display-active sleep, native
USB4 NVMe, physical disconnect during sleep, write verification and power
measurement remain untested by these runs.

Harness notes: initial Test154 preflight ran before USB storage enumeration
finished and stopped before suspend. Test156 initially checked NVMe too early
after asynchronous re-enumeration; a separate verification then checked the
saved baseline hashes. Neither preflight failure is presented as a kernel fix.
A transient USB2-hub address setup error -71 at boot recovered by retry and
is retained in the journal. No SError or storage I/O error was observed in
these PM tests. This is not a claim that the entire journal is error-free.
