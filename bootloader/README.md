# Separate boot environment: Asahi Linux

The requested Apple boot-picker name is exactly **Asahi Linux**. This is the
name of a new APFS boot container, not a replacement name for every GRUB entry.
The intended environment offers internal Linux, external USB sticks/USB SSDs,
and external Thunderbolt PCIe NVMe through GRUB. Distribution, drive model and
UUID may distinguish the individual GRUB entries. Fedora and Ubuntu remain
distinct systems; this name does not claim that either is already installed.
The new GRUB menu is to remain visible for ten seconds, with the internal
fallback available even when external media are absent. This is distinct from
U-Boot's ten-second interruption window. The current Ubuntu menu is unchanged.

## Current implementation boundary

This directory contains a pinned U-Boot development profile and a build-only
script. It preserves Apple internal NVMe and USB mass-storage support and adds
the generic PCIe NVMe driver. **It does not implement Thunderbolt boot.**
No APFS container, ESP, Apple boot policy, GRUB installation or live boot bundle
has been created or changed by this work. This is not an installable release.

The read-only check on 2026-10-31 found installed `u-boot-asahi 2025.10-2-1`
with `CONFIG_NVME_APPLE=y` but `CONFIG_NVME_PCI` disabled. The upstream source
pinned in `profile.json` has `boot_targets=nvme usb` and an Apple PCIe driver,
but no Apple USB4 connection manager / PCIe-C tunnel initialization path.
Adding `NVME_PCI` closes only the final storage-driver gap. USB4 preparation
in m1n1 for Linux is not an implementation of boot-time tunnel discovery.

The Mac's internal GPT has **zero unallocated sectors**. A separate boot
container therefore needs a deliberate space-allocation step through Apple's
macOS/recovery tools. Free space inside Linux `/` is not unpartitioned space.
The existing Ubuntu boot container and its known-working boot bundle are the
fallback and must remain independently bootable.

## Reproducible build

Use a clean checkout of the commit in `profile.json`, an AArch64 cross compiler,
and the normal U-Boot host build dependencies:

```sh
bash bootloader/build-uboot.sh /path/to/u-boot /path/to/new-output-directory
```

The script refuses another source commit, tracked source edits or an existing
output directory. It checks that internal NVMe, USB and EFI-loader support
remain enabled. It produces hashes and an explicit development status in
`build-result.json`; it never creates `boot.bin` or installs anything.
The Apple-menu name is applied later by the official Asahi bootstrap process;
it is not embedded by renaming the U-Boot binary.

## Remaining development and acceptance checks

1. Implement the minimal Apple USB4 host/router setup and PCIe tunnel needed
   for storage. Reuse documented behavior and appropriately attributed open
   source, with bounded waits and diagnostics. Do not silently authorize all
   peripherals: define an explicit boot-device selection policy.
2. Integrate PCIe-C enumeration, bridge resources and DART mappings before NVMe
   enables bus mastering. The existing internal PCIe driver is not sufficient.
3. Prove read-only access to a known external TB NVMe partition and compare
   file hashes. A successful build or `nvme scan` command alone is insufficient.
4. Export the external disk through U-Boot EFI block I/O for GRUB. Retain
   internal/USB access if no TB disk is present or tunnel setup times out.
5. Quiesce DMA and coordinate teardown/handover so Linux can safely initialize
   the same controller. Test cold start, warm start, missing TB disk and both
   Mac ports; then boot from internal, USB and TB media separately.
6. Only after validation create the separate **Asahi Linux** APFS stub and
   system ESP using the official Asahi installer/Recovery authorization flow.
   Keep the target Linux kernel and initramfs on their chosen target medium.

GRUB should select filesystems by UUID, not transient disk numbers. It must use
each target's own kernel, matching initramfs and root UUID. A shared firmware /
device-tree baseline must be checked against every supported target kernel;
independent distros must not overwrite the shared `m1n1/boot.bin` independently.
The existing experimental installer still requires its current arming flow;
this profile does not remove that restriction or enable TB installation there.

## Sources

- [Asahi boot chain](https://asahilinux.org/docs/alt/boot-process-guide/)
- [UEFI-only bootstrap and OS layout](https://asahilinux.org/docs/platform/open-os-interop/)
- [Asahi U-Boot](https://asahilinux.org/docs/sw/u-boot/)
- [Pinned U-Boot source](https://github.com/AsahiLinux/u-boot/tree/b33034a515a068381c4aa28831fb709e91300cd1)
- [Official UEFI-only build workflow](https://github.com/AsahiLinux/asahi-installer/blob/e93743d52178b3e26e428fa05174ef549abf30cb/.github/workflows/uefi-only-build.yaml)

## Tested prototype, separate from the feature-only profile

`build-prototype.py` applies the patches pinned in `prototype.json` in a fresh
worktree, builds the sandbox tests, and cross-builds the Apple M1 profile. It
preserves internal NVMe, USB storage and EFI loading. The source/patch hashes
and results are recorded under `validation/`. No `boot.bin` is assembled or
installed. Example:

```sh
python3 bootloader/build-prototype.py /path/to/clean-pinned-u-boot /path/to/new-output --jobs 4
```

The patches repair PCI IOMMU association for enumerated endpoints without their
own device-tree nodes and add a USB4 DART register-layout prototype. Register
unit tests emulate memory-mapped registers, not real DMA, ACIO firmware or
Thunderbolt links. See the [evidence crosswalk](sonoma-and-linux-crosswalk.md)
for the actual reuse of Sonoma captures and the consolidated Linux patches.

`test-qemu-storage.py` separately tests generic NVMe and USB storage using a
new regular-file disk image in QEMU. It verifies a 5 MiB + 23 byte file hash and
executes an external EFI test program, including USB access when NVMe is absent.
This validates the generic storage/EFI route only; QEMU does not emulate Apple's
USB4 controller or DART and this is not a GRUB-to-Linux hardware boot test.

The tested binaries and complete build logs are additionally archived locally.
The development prototype must not be offered as an installer kernel release.

### Additional prerequisites tested on 31 October

The prototype also bounds Apple mailbox queue waits: an emulated permanently
full queue first reproduced an unbounded wait in the original driver, then
returned `-ETIMEDOUT` with the change. A later send succeeds once the queue is
available. A timeout after submission does not prove that firmware never saw
the message; callers must not blindly retry non-idempotent commands.

The USB4 packet library encodes configuration read/write requests and validates
normal replies (wire order, CRC32C, length, route, sequence and register range).
It deliberately permits the reply's upstream port to differ from the requested
port, matching the Linux control protocol. It has **no NHI transport**, event
handler, router discovery or PCIe tunnel activation. Its tests use fixed wire
vectors and injected corruption, not a physical USB4 controller.

DART allocation tests reproduced two more problems: a zero-length request was
accepted, and an exhausted IOVA allocator still caused page-table writes. The
sixth patch rejects empty/overflowing/out-of-aperture mappings, checks IOVA
allocation failure before touching tables, bounds unmap ranges, and checks
page-table allocation results. Zero denotes failure for this DART translated
aperture, which excludes zero. This is **not** a completed generic U-Boot DMA
error API: callers still need to check errors, and flush-timeout propagation
and safe teardown remain open. Allocation-failure branches are reviewed and
compiled; heap-allocation fault injection has not been performed.

GitHub's `U-Boot development checks (no installation)` independently applies
all pinned patches, runs the sandbox tests and cross-builds the Apple profile.
It publishes no bootloader release and changes neither kernel Latest nor the
installer. Local `validation/prototype-result.json` records the exact tested
patch hashes; changing a patch invalidates that recorded result until rebuilt.

### First M1 hardware regression check

On 31 October the six-patch prototype, loaded only into RAM under the m1n1
hypervisor, read known files from the **real internal NVMe and SanDisk USB**
media. Both SHA-256 digests matched. Virtual UART captured the result and
regular internal Ubuntu returned after reset. See
[the scoped result](validation/m1-storage-probe-20261031.json) and
[U-Boot output](validation/m1-storage-probe-20261031.log).
This establishes existing-storage regression coverage, **not Thunderbolt
tunnel support, native GRUB boot or Linux handover**. The diagnostic device
tree omitted the unused GPU alias because AGX firmware initialization on the
Sonoma Test bootstrap rejected firmware 14.7; the known HDMI bootstrap failure
was avoided by recording the virtual UART. No installed boot files changed.

### Apple I2C and Type-C hardware status

The seventh patch adds bounded polled Apple/PA Semi I2C transfers, retaining
upstream Linux attribution. It supports short 7-bit transfers and combined
register reads; rejects unsupported transactions before the first bus write;
and reports NACK, arbitration, FIFO and timeout failures. Six sandbox tests
cover read/write ordering, maximum read size, invalid combined transactions,
timeouts and error recovery. The complete seven-patch build passes 43 tests
and cross-builds the M1 profile.

On the real M1, the same diagnostic U-Boot image read CD321x registers with a
SanDisk attached, then with an OWC Express 1M2 attached. The controller reported
USB mode for the former and its USB4 connection flag for the latter. Internal
NVMe file hashes passed in both runs; the SanDisk file hash also passed.
See [SanDisk evidence](validation/m1-typec-probe2-20261031.json) and
[OWC evidence](validation/m1-typec-probe3-20261031.json), with adjacent UART logs.
The OWC was **not read as a disk**. PHY, ACIO/NHI and PCIe tunnel setup are still
missing. One optional Intel-status read was shorter than its advertised block
length and is retained only as raw evidence, not decoded as a complete record.

All three hardware runs used RAM-only payloads under m1n1; the installed boot
bundle remained unchanged and internal Ubuntu returned after each reset.
The broad `hardware_tested: false` manifest flag means the complete prototype
feature set is not hardware-validated; `hardware_tested_scope` identifies the
specific storage and Type-C checks that have passed.

### Structured CD321x status query (development)

The eighth patch provides `cd321x <bus-decimal> <chip-hex>` for explicit M1
controller addresses `38` and `3f`. It performs register reads only: no bus scan,
4CC reset, mode change or tunnel activation. It requires the observed Apple
vendor ID, APP firmware mode and exact known register lengths. A second data
status read detects a change during the sample; failure leaves the caller's
result unchanged. Sequential sampling is not an atomic guarantee against a
cable change immediately afterwards.

Five tests use the real SanDisk and OWC byte vectors and inject wrong lengths,
transport timeouts, incorrect identity/mode, changing status and bad command
arguments. Unknown firmware layouts are rejected; this initial decoder is not
claimed to support every CD321x revision. Neither this command nor the I2C
patch changes the installed kernel or its excluded ACK-timeout handling.

The structured command also passed twice on the real M1 with the OWC attached:
[probe 4 evidence](validation/m1-typec-probe4-20261031.json). m1n1 supplied the
AXI2AF, common and both CIO-lane calibration properties (120, 1092, 852 and
852 bytes respectively). These are presence/length observations, not proof
that U-Boot has applied or validated the full calibration arrays. The internal
NVMe hash passed again and the guest executed its reset command.
