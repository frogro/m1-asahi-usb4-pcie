# Integrated M1 U-Boot: native TB3 and USB4 EFI boot

This is the complete U-Boot build with the previously tested Apple PHY, ACIO,
NHI, DART, PCIe-C, NVMe and EFI handover work integrated as a pinned twelve-patch
series. It retains internal Apple NVMe, USB mass storage, EFI and standard
bootflow. It is not the old eight-patch, feature-only prototype.

The transport now scans GPT EFI system partitions and loads the standard
`/EFI/BOOT/BOOTAA64.EFI`. It contains no installed-system UUID, partition number,
kernel version, initramfs filename or expected executable digest. GRUB and its
configuration select each installed OS and its own kernel/initramfs. Normal
U-Boot EFI executable validation/security policy applies; removing the
experiment's hardcoded hashes does not add Secure Boot.

Native Linux handover enables both Mac ports. The obsolete hypervisor debug
port reservation is gone. NVMe DMA, NHI and ACIO are still quiesced before
ExitBootServices, and failure aborts handover. The TB block device and EFI
media remain read-only. After a failed setup that changed hardware, reset to
the independently preserved default Apple boot entry is intentional; unsafe
continuation through a partly active controller is not allowed.

## Confirmed and remaining scope

The `20261101-usb4-integrated-rc3` build automatically selects TB3 or USB4
from the validated Type-C cable state. The normal U-Boot main loop and read-only EFI/NVMe reader are retained.
Patch 12 adds an explicit halt of the separately retained USB4 xHCI context
before NHI/ACIO shutdown at ExitBootServices. Failure prevents Linux handover.
Generic USB teardown cannot discover that removed device-model context.
This source-level ownership fix is not claimed to explain the intermittent
black-screen return into the original stock Ubuntu. Runtime dispatch
is exclusive and no longer requires numbered diagnostic tunnel-stage flags.

The MP400 (ASM2463) with Samsung 970 EVO Plus booted the unchanged
`7.2.12-usb4sd4-egpu3` kernel and external NVMe root. Both 64 MiB direct reads
matched the earlier known digest; the Dynabook and all four Radeon functions
were bound. A second boot used the normal root-authorization overlay without
diagnostic capture hooks. rc3 also reached that external root after the xHCI
handover correction. This is native USB4, not USB mass-storage fallback. Visual GRUB
confirmation was not obtained for this run. Earlier rc1 TB3/internal/USB results
below remain historical evidence, not an assertion that all were retested on rc3.

**Universal boot remains the goal, not a claim of completed compatibility.**
The pre-OS tunnel is restricted to J274 M1 port1, a direct USB4 v1 router or
the previously supported Intel Alpine Ridge (8086:15da) TB3 topology, and one
NVMe namespace. USB4 adapters are discovered and validated; they are not fixed
to the MP400 port numbers. The single PCIe tunnel allocates the validated
minimum lane credits and preserves vendor-defined protocol-adapter fields.
USB4 v2, downstream router chains, port0 pre-OS tunnels and multiple namespaces
remain unvalidated. The normal USB path does not force a USB4 device to USB3.

### External-root authorization belongs to Linux

U-Boot reads external EFI/GRUB, kernel and initramfs, then relinquishes the
controllers. Linux must independently authorize the selected root enclosure.
The original external initramfs only allowed the earlier Intel TB3 Yotta, so
MP400 appeared as an unauthorized router and the root device timed out.
No new kernel compilation was needed to correct that distinction.

`make-root-auth-overlay.py` generates a dracut settled hook for explicit
root UUID, router UUID, vendor/device IDs and physical SoC controller.
It refuses to authorize a different device or a boot using another root.
It performs at most one authorization attempt per boot, has no diagnostic
command-line dependency, and mounts/writes no boot filesystem. It only creates
an archive; installation and GRUB selection must be performed separately after
checking the actual selected device. Retain the original initramfs as fallback.
Do not reuse this Mac's UUIDs from the hardware evidence on another system.

## Rebuild and checks

```
python3 bootloader/integrated/build.py /path/to/u-boot /path/to/new-output --jobs 4
```

The script checks every patch hash, reconstructs the source in an isolated
worktree at the pinned upstream commit, builds the full Apple and sandbox
profiles, runs hardware-library tests, actual C EFI/FDT fault tests and the
USB4 router/path/transport-dispatch fault tests. It
never changes installed boot files or builds/updates a kernel. m1n1 source
is not modified. The independently installed Apple `Asahi Linux` entry uses
the unchanged released m1n1 stage2 binary plus the integrated DT and U-Boot.

`j274-integrated.dts` is the current M1 profile, including the exact validated
Linux/boot-stage tunables. The remaining numbered configuration properties
select previously proven low-level initialization stages; they are not
claims of universal hardware support. The startup command is `tbboot`, not
the old script that hashed one internal file and loaded named test artifacts.

`grub.cfg` and `grub-bootstrap.cfg` are this Mac's installation-specific menu
examples, deliberately separate from the U-Boot transport. Do not reuse their
filesystem UUIDs on another installation. They retain the internal Ubuntu
menu and SanDisk menu alongside external desktop/text choices.

## Deferred kernel findings (boot work has priority)

Boot 1 (`efd64b11-f5a6-42fe-a131-354b93bb87d1`) logged PCIe tunnel reset-release
timeouts on both hosts at about 7.04 seconds and again on port0 at 12.11
seconds. Later enumeration succeeded, including the root SSD and all Radeon
functions. Keep these messages and timestamps in the evidence: this run
neither proves them harmless in all cases nor justifies suppressing them.
No ACK-timeout filtering patch is added. The earlier audio mutex correction
is queued separately and was not installed during these bootloader tests.

## Hardware boot matrix, 2026-11-01

The same installed bundle passed three TB-root starts, an internal stock Ubuntu
start via its existing GRUB menu, and a SanDisk USB-A start via its existing
GRUB menu. See `hardware-validation.json` for boot IDs and kernel differences.
The USB comparison used kernel/initramfs and root from SanDisk, while the first
EFI/GRUB stage still came from the TB SSD. A subsequent start with the TB SSD physically disconnected also passed;
see the independent USB acceptance below. The original Apple Ubuntu default and bundle are
unchanged. The independent Asahi entry was selected only for the next boot.

Both later egpu3 boots bound all four Radeon drivers, but all Radeon display
connectors read disconnected. This is a recorded system finding, not a claim
that dual-monitor graphics passed every reboot. No new GPU or audio patch
was installed to hide or change this observation.

A fourth TB-root start also reached SSH on egpu3, and `grub2-common` succeeded
there. The following ordinary reboot to the original Apple default did not
return on either network address and HDMI stayed black. Recovery was requested;
shutdown versus firmware/next-boot failure is not yet localized. The repeated
boot/shutdown sequence therefore does **not** have an all-passed result.

## Independent USB3 acceptance

Boot `cbc184c2-98e9-4c4b-babd-1674e4de8e9c` started SanDisk on the Mac USB-A
port with Yottamaster physically disconnected. The unchanged integrated
U-Boot took normal bootflow, and the independent Asahi ESP GRUB loaded
kernel, initramfs and root from SanDisk. Linux reported the expected
`20261101-efi-rc1` marker, USB root and zero failed system units.

The independent Asahi ESP now holds a standalone GRUB menu (example
`independent-esp-grub.cfg`) with internal Ubuntu, USB SanDisk and TB Samsung
choices. Only GRUB is stored there, not a kernel or initramfs. Its previous
BOOTAA64.EFI is backed up on the same ESP; the original Ubuntu ESP/bundle
remain unchanged. The SanDisk retains older egpu1 kernel/firmware and is not
a current-kernel regression acceptance. Native USB4 was subsequently integrated in rc2; see the current scope above.

The earlier black-screen return is now localized past GRUB: the original
internal stock 7.2.0 kernel and userspace began, and that journal ends at
4.9 seconds, near an ACIO AT-register timeout. This does not establish the
root cause or exclude retained hardware state. Manual original-Ubuntu
recovery succeeded.

## Current reboot limitation

The first rc2 return to the original internal Ubuntu succeeded. The next
external shutdown was orderly through journald termination, and the subsequent
internal boot reached its stock kernel, system services and GDM, but HDMI was
black and SSH unavailable. Manual original-Ubuntu recovery succeeded. This
localizes the observed return failure past GRUB; it does not identify its cause.
The rc3 external-root boot and subsequent automatic return to the internal
stock Ubuntu were confirmed over SSH; repeated reboot stability remains open.
The transient `grub2-common` invalid-environment-block report could not be
reproduced against the same external `grubenv` offline; it was not erased or
silenced. These findings are retained separately from successful USB4 boot.

The currently installed kernel, its modules and its original initramfs were
not rebuilt/replaced during this integration. The selected-root initramfs is
an additional file; the original remains available. Initial hardware tests used one-shot selection and restored the preceding
independent Asahi bootloader. After the USB4 and independent USB3 acceptances,
rc3 was installed in the independent Asahi entry with verified rollback copies.
The original Apple Ubuntu default and its bundle remain unchanged. The external
menu example now uses the additional selected-root initramfs for both Samsung
entries; generate it for the actual enclosure, not by copying these UUIDs.

## rc3 independent USB3 comparison

With MP400 physically disconnected, the same twelve-patch rc3 bundle booted
SanDisk through the normal USB/internal EFI path. Linux confirmed the rc3 DT
marker, USB root and a 5000 Mb/s UAS link (boot
`523b5ee3-fe76-4659-96c8-65d4b184557b`). The user confirmed the Ubuntu login/desktop
and logged in. Zero system units failed, and the previous independent Asahi
bundle was automatically restored. This retains the existing USB3 boot option
without a Thunderbolt/USB4 system disk. The older SanDisk egpu1 image still
reports its known missing AVD firmware and a PCIe tunnel reset timeout; this
is a bootloader regression test, not acceptance of that older full system.

The installed rc3 bundle SHA-256 is
`212f460d8b2df1108c237b4c7f239107a04104aa9f33f1eb1cf57f99bd18dd9e`.
On this Mac, backups are in `/var/lib/asahi-integrated-rc3-20261101`, plus
`m1n1/boot-before-usb4-rc3.bin` on the independent Asahi ESP and
`grub/grub-before-usb4-rc3.cfg` on the external boot partition. No kernel or
initramfs was copied to the internal boot partition. See the installation
manifest and boot evidence before extending the hardware compatibility claim.

The regular installed Samsung text entry passed a further boot and automatic
return to the original internal Ubuntu. The user observed its GRUB menu and
text console. rc3 remains installed in the independent Asahi entry, and the
test return/restore timers are disabled. A guarded rollback helper is stored
with the internal backup directory; no automatic rollback remains armed.
