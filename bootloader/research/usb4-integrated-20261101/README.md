# Native USB4 integration into the full M1 U-Boot

The eleven-patch rc2 and twelve-patch rc3 series extend the previous full
TB3/USB/internal bootloader. These are complete U-Boot builds, not a replacement
of `common/main.c` with a diagnostic program. The original Apple Ubuntu entry
and its bundle remain unchanged. The initial hardware candidates were selected once and the preceding
independent Asahi bundle restored after Linux started. After acceptance, rc3
was deliberately installed with rollback copies, as recorded below.

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

The five-minute SanDisk return completed automatically to internal stock Ubuntu
(boot `7c714ad2-1518-4166-8145-c0af2c6b4ecc`). Both fallback bundle hashes were
verified and the one-shot return/restore units were disabled afterward.

## Regular installed boot and GitHub verification

After both transport acceptances, rc3 was deliberately installed in the
independent Asahi entry, with verified backups on the internal root and next
to each target file. Both regular Samsung menu entries now use the additional
selected-root initramfs. Kernel and original initramfs remain unchanged.
`installation.json` records exact installed hashes.

Boot `8caed138-f834-46bb-b7e0-9860872a10f1` used the regular text entry, reached
external NVMe root and SSH, and bound the dock and four Radeon functions. The
user confirmed the Samsung GRUB menu and text console. No system units failed.
The original Ubuntu Apple default remains the fallback.

This boot logged `apple-sio: late IOMMU probe at driver bind` followed by
`__device_links_no_driver`. These warnings were not present in the preceding
captured rc2/rc3 logs. The limited journal search on the external system found
them only in this boot. Their cause is unestablished; successful boot does not
make them an all-clear. No kernel ordering patch or warning suppression was
introduced. Existing PCIe reset-release and IRQ-parse messages remain visible.

GitHub run 41334500476 at commit 26c80f3 passed both prototype and integrated
jobs. Unlike the earlier incremental local report, that integrated CI job ran
the full twelve-patch reconstruction, builds and all configured checks in one
run. See `github-ci.json`.

A later direct read of the entire 65,260,032-byte kernel file matched its
original SHA-256 (`24d6f4ea…`), the root remained read-write, and no additional
kernel warnings appeared after initialization at that check. The MP400 was
identified by router UUID, not unstable domain numbering: it negotiated two
20 Gb/s lanes in each direction on `501ac0000.cio`.

## Follow-up priorities kept separate from boot acceptance

1. Intermittent black-screen/no-SSH return after stock internal Linux starts.
2. The newly observed SIO/IOMMU and device-link initialization warnings.
3. PCIe tunnel reset-release timeouts despite later successful enumeration.
4. Repeated `of_irq_parse_pci: failed with rc=-22`; verify complete interrupt
   setup rather than hiding the messages.
5. The single invalid GRUB environment report from `grub2-common` in running
   Linux, not reproduced offline or in later boots. This is boot-configuration
   management evidence, not a demonstrated pre-Linux GRUB failure.
6. Earlier desktop resume/black-screen and WirePlumber shutdown findings are
   outside these boot-only acceptances; they have not been declared fixed.

No new ACK-timeout filtering, GPU reset policy or kernel patch was introduced
during this bootloader consolidation.

The regular installed boot also returned automatically to the original
internal Ubuntu (boot `9f115de9-da96-4963-92ae-204f112633dd`). The independent
Asahi bundle still matched rc3 after that return; its previous bundle and the
original Ubuntu bundle matched their expected digests. Test return/restore
units are disabled and temporary mounts are gone. A guarded rollback helper
is saved on the internal system at
`/var/lib/asahi-integrated-rc3-20261101/rollback.py`; it must be run explicitly
from the original internal Ubuntu and refuses independently changed targets.
It was syntax-checked but deliberately not executed, since rc3 is the accepted
installed candidate.
