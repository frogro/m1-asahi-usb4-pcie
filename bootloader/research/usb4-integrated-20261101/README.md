# Native USB4 integration into the full M1 U-Boot

The eleven-patch rc2 and twelve-patch rc3 series extend the previous full
TB3/USB/internal bootloader. These are complete U-Boot builds, not a replacement
of `common/main.c` with a diagnostic program. The original Apple Ubuntu entry
and its bundle remain unchanged. The hardware candidate is selected once and
the preceding independent Asahi bundle is restored after Linux starts.

## Boot evidence

Three native MP400 USB4 starts reached the external Samsung NVMe root, using
the existing `7.2.12-usb4sd4-egpu3` kernel. `result.json` records boot IDs,
return results and the limits of the evidence. The known 64 MiB direct-read
SHA-256 matched. The dock and four Radeon functions bound in Linux; that is
not a new rendering, audio or hot-unplug acceptance test. Visual GRUB output
was not independently confirmed by the user in these runs.

The first rc2 boot retained the preceding diagnostic initramfs. The second rc2
and rc3 boots used an additional initramfs consisting of the original archive
plus a narrowly scoped selected-root authorization hook. This is necessary
because Linux reconstructs its own tunnel after U-Boot relinquishes the
controllers. The original archive only authorized the earlier Intel TB3 Yotta;
it did not authorize this MP400 router. The new hook does not need a diagnostic
kernel argument, record kernel logs, or mount/write an ESP. It checks the root
UUID, physical controller, router UUID and vendor/device before one attempt.
The original kernel, modules and original initramfs were not replaced.

## Retained xHCI ownership correction

The USB4 boot setup removes the ordinary USB device-model device, then starts
an xHCI context retained outside that model. Generic EFI USB teardown cannot
find that context. The earlier cleanup was after a call that does not return
on successful EFI/Linux handover. Patch 12 explicitly halts this controller
and verifies HALTED before NHI/ACIO teardown and Linux DMA-memory reuse. Failure
blocks handover through the existing reset path. Allocated DMA buffers remain
reserved until handoff. TB3 without that context is a no-op.

This is an independently identified source-level gap. It is **not** proof that
this gap caused the intermittent black-screen return to the original Ubuntu.
After rc3 the external boot and the automatic return to the internal root were
confirmed over SSH, but one successful cycle is not complete reboot acceptance.

## Return failure retained in the record

The first rc2 return succeeded. After the second rc2 test, external Linux shut
down through root unmount and journald termination. The next internal stock
kernel boot reached services and GDM, but HDMI was black and SSH unavailable.
Manual recovery succeeded. That localizes this instance beyond GRUB but does
not establish its cause or exclude retained controller state.

The second rc2 boot also logged `grub2-common` reporting an invalid environment
block. The same 1024-byte external `grubenv` had a valid header and could be
read offline with `grub-editenv`; it was not erased or replaced to hide the
finding. `grub2-common` succeeded on rc3.

## Software evidence and limits

`eleven-patch-clean-build.json` records reconstruction from the pinned upstream
commit, full Apple and sandbox builds and the protocol tests. Patch 12 then
applied to that clean reconstruction and passed the Apple and sandbox builds
(`clean-rc3-build.log`, `clean-rc3-sandbox-build.log`), followed by the 19 affected
PHY/PCIe sandbox cases (`twelve-patch-validation.json`). All six changed source files matched the hardware-tested
source (`rc3-source-reconstruction.json`). The additional actual C handover
fault test covers ordered teardown, every failure barrier, idempotence and the
TB3 no-op with ASan/UBSan. Root-authorization tests exercise wrong-device,
wrong-root, already-authorized and retry conditions. The current `build.py`
includes these checks for future complete twelve-patch builds. Do not mistake
the earlier eleven-patch build report for an uninterrupted twelve-patch run.

Current pre-OS scope is J274 port1, USB4 v1 with one direct external router or
the guarded Intel Alpine Ridge TB3 topology, and one NVMe namespace. Adapter
ports are discovered and validated rather than copied from MP400 numbering.
The EFI reader is read-only and selects standard GPT EFI executables, without
hardcoding an installed system, root UUID, kernel or initramfs. Installation
examples and the selected-root hook are separate from that transport.

OWC, downstream router chains, USB4 v2, pre-OS port0, multiple namespaces and
the new rc3 TB3 hardware regression remain unvalidated. The previous rc1
hardware results remain historical evidence, not a substitute for these tests.

## Independent USB3 comparison on rc3

The user disconnected MP400; its filesystem UUID disappeared from the internal
Ubuntu device inventory before the test. The new rc3 bundle then started the
unchanged SanDisk egpu1 system on USB-A. `sandisk-system.txt` records the rc3
marker, external USB root, 5000 Mb/s UAS link, successful restoration of the
previous loader and zero failed system units. The user confirmed a visible
login/desktop and logged in. Existing egpu1 AVD/reset-timeout messages remain
in the evidence and were not treated as USB boot failure or suppressed.

Published text logs have terminal escapes and trailing whitespace removed;
original captures are retained in the local test directory.
