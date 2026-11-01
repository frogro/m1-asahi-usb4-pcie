# Integrated M1 U-Boot: native Thunderbolt EFI boot

This is the complete U-Boot build with the previously tested Apple PHY, ACIO,
NHI, DART, PCIe-C, NVMe and EFI handover work integrated as a pinned ten-patch
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

The first native hardware boot of `20261101-efi-rc1` reached Ubuntu on the
Samsung 970 EVO Plus through the Yottamaster TB3 enclosure. The unchanged
`7.2.12-usb4sd4-egpu3` kernel bound the Dynabook and all four Radeon functions
on the other Mac port. The user saw two monitor outputs. See validation
records for subsequent boots; a build passing is not hardware coverage.

**Universal boot remains the goal, not a claim of completed compatibility.**
The low-level tunnel implementation is still restricted to J274 M1 port1,
a direct Intel Alpine Ridge (8086:15da) TB3 storage topology and one NVMe namespace. Native USB4 enclosure
link setup, boot-time tunnels on port0, multiple endpoints/namespaces and
other Apple models remain open. Enabling port0 for Linux is not proof of
pre-OS port0 tunnelling. The existing USB path remains available for USB
storage; it does not force an already negotiated USB4 device into USB3.

## Rebuild and checks

```
python3 bootloader/integrated/build.py /path/to/u-boot /path/to/new-output --jobs 4
```

The script checks every patch hash, reconstructs the source in an isolated
worktree at the pinned upstream commit, builds the full Apple and sandbox
profiles, runs hardware-library tests and actual C EFI/FDT fault tests. It
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
EFI/GRUB stage still came from the TB SSD. A cold start with no TB device
attached remains untested. The original Apple Ubuntu default and bundle are
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
