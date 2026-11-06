# Local Googlebook image inputs

No Android system/vendor/firmware/account data, ADB keys or full disk images are
stored or built in public CI. The kernel workflow only builds GPL kernel sources
and modules. `assemble-initramfs.py` builds a local candidate from a hash-pinned
prepared M1 Android base and matching EROFS module images. It does not overwrite
that base or any partition, and preserves the Android init, SELinux policy,
authenticated ADB setup and unrelated archive entries.

Create a private JSON profile with `kernel_release`, `selected_router`,
`selected_super` (super PARTUUID), `selected_dock` (router UUID), and `sha256`
containing `base`, `vendor_dlkm`, `system_dlkm`. Obtain these from the selected
disk and verified build artifacts, never from enumeration indices. Then:

```sh
python3 assemble-initramfs.py private-profile.json prepared-base.img \
  matching-vendor_dlkm.erofs matching-system_dlkm.erofs candidate.img
```

Dependencies: Python3, ARM64 static C toolchain, erofs-utils and kmod. Module
vermagic and the preload list are checked against the selected release. The
bootstrap validates the kernel ABI and selected Android partition at runtime,
preloads storage/network modules and keeps both read-only module loops alive
through Android's ramdisk cleanup. The ancestor guard is supplied by the new
kernel; the matching router UUID is passed before loading thunderbolt. The
known direct/single-dock profile is parameterized here without expanding its
hardware scope. This does not claim arbitrary nested topology support.

The prepared M1 base and module EROFS images remain explicit local inputs.
Regenerating the whole proprietary Android system from source is not provided.
Keep the matched existing vendor and firmware together. Audio plus removable
storage is the vendor-fstab-only patch in `../next-build/removable-usb`; preserve
EROFS modes, ownership and SELinux xattrs and compare the full inode inventory.
Do not apply that broad USB-SCSI rule to a USB-root profile until the boot disk
is explicitly excluded. Never accept a format prompt for an existing disk.

Retain the previous complete disk image and the matching initramfs/vendor before
installation. A full local disk backup remains a separate offline operation,
not part of a public build or this non-installing ramdisk assembler.

## Build the matching module inputs

Use the unpacked kernel package and the full firmware directory from the working
local Googlebook setup (including Apple, Broadcom and any selected GPU firmware):

```sh
python3 build-module-images.py unpacked-kernel matched-private-firmware module-output \
  --vendor-overlay locally-extracted-working-vendor-dlkm \
  --release 7.2.12-googlebook-usb4-egpu2
```

This decompresses modules, reruns depmod against the matching System.map, checks
vermagic, resolves the early preload order from the new dependency graph and
builds both EROFS images with the original Android SELinux labels. Use an
erofs-utils build that supports `--file-contexts`; there is no fallback that
silently discards labels. Supply `--preload module-output/preload.inc` to the
ramdisk assembler and pin the resulting image hashes in the private profile.
The required local overlay preserves Android init services outside `lib/modules`;
in particular the boot entry imports `etc/init/googlebook-main.rc`. Compare these
files and their on-image metadata against the working image before installation.
Firmware and complete generated images remain on the local machine.
