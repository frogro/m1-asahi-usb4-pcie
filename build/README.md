# Consolidated kernel build — no installation

This workflow builds a complete ARM64 `Image`, all modules selected by the running Mac kernel configuration, and DTBs. It runs on a hosted Ubuntu 26.04 ARM64 runner. Nothing connects to the Mac or changes installed kernels, modules, firmware, bootloader or boot defaults.

## Inputs

- UbuntuAsahi/linux commit `f7734f4c91c0f47d9e762786968057bec99a0788` (Linux 7.2.12).
- `running-kernel.config`: read from `/boot/config-7.2.0-1001-asahi-arm` on 30 October 2026.
- 29 patches in `consolidated/20261030`, including storage/PCIe/USB4 and dock video/audio plus whole-dock retirement. Preimage, patch and final file hashes are checked against the real Git base before compiling.
- By default, the experimental AMDGPU/TTM/eGPU modifications are excluded. With `include_egpu=true`, 16 patches in `consolidated/egpu179` are appended after verifying their source preimages; the result is `7.2.12-usb4sd4-egpu3`. See that directory's README for hardware evidence, required diagnostic parameters and remaining integration limits.

The new release is `7.2.12-usb4sd3`. Existing enabled options must remain unchanged after `olddefconfig`; changes to compiler metadata and release identification are reported separately. `PCIE_APPLE_PCIEC=y` is added. Public Ubuntu trust/revocation certificates are assembled using the source packaging rules. Modules are signed with a newly generated build key, not Canonical's private key. The private signing key is not exported.

## Outputs

The workflow stores results as assets of a draft release in this repository (draft assets require repository access). It does not use Actions artifact or cache storage. Files exceeding the release asset limit are split into numbered `.partNNN` pieces; concatenate them in numeric order before extraction.

- `linux-7.2.12-usb4sd3-arm64.tar.zst`: kernel Image, System.map, configuration, DTBs and all matching staged modules, with module debug symbols stripped and BTF retained.
- Compressed `vmlinux` with the configured debug information.
- Configuration comparison, module list/vermagic, Module.symvers, public signing certificate, applied commit metadata, build log and SHA-256 hashes.

The archive is not an installer and contains no initramfs or modified m1n1 boot image. The experimental [external installer](../installer/README.md) separately prepares these for a later hardware test. Other installations must separately prepare a matching initramfs and the existing Asahi boot pipeline, keep all current kernels, and use an explicit additional boot entry.

When AVD is enabled, the build now includes all six Apple video decoder firmware variants under `usr/lib/firmware/apple`, built from AsahiLinux/avd-fw commit `c870554fce20b9ee5ac46885c698d11e6a313948` with all codecs enabled. The firmware license and source/hash manifest are included; a separate firmware archive and Debian package allow installation without rebuilding the kernel. Missing firmware or incorrect variant sizes fail the build. The first Yotta installation had omitted this separate firmware, causing AVD probe error -2. Other machine-specific vendor firmware and AMD firmware must still be supplied by system preparation.

The local `avd-firmware-layout.patch` explicitly places ARM unwind sections after code/data. With LLD 21, leaving these sections orphaned put `.ARM.exidx` at zero and moved the Cortex-M vector table to 0x18; that first build compiled but failed the AVD boot handshake. Package revision 2 corrects the layout. Build checks now require the vector table at zero, the expected initial stack and a valid Thumb reset vector, as well as sizes and hashes. Hardware loading must still be verified after a fresh boot because the driver retains the runtime-PM error from a failed firmware start.

The archive also supplies an `apple_dcp` UCM profile for the digital display PCM and HDMI/DP jack. It does not alter `macaudio` speaker safety or equalization. Both digital cards accepted the profile on the Mac mini J274; audible output remains a separate functional check. On 31 October 2026, package revision 2 passed a fresh-boot hardware decode on the J274 running `7.2.12-usb4sd4-egpu1`: an explicit GStreamer `v4l2slh264dec` pipeline decoded all 48 H.264 baseline frames (320×240) with no AVD errors. Its 5,529,600-byte I420 output matched the software reference byte for byte (SHA-256 `f3ff610f6a19137cf22847a07e786b32b81b92646d089810796ebed97a8a26f5`). This verifies that stream and firmware variant; it does not certify every codec or resolution.

The final three patches add automatic retained-power suspend-to-idle handling for the PHY and ACIO/NHI plus its validation record. Matching diagnostic modules passed Tests154–157. A boot of the complete 29-patch kernel remains pending; active-link deep suspend/hibernation and controller power-loss recovery remain unsupported. Reset ACK classification changes are excluded. A passing build does not certify hardware stability. The consolidated patches preserve source attribution; no upstream PR is created by this workflow.

## Running

Start **Consolidated M1 kernel (build only)** with `workflow_dispatch`. The workflow uses standard hosted ARM64 resources, at most one concurrent job, and a six-hour timeout. It checks free storage before building and does not remove any user data or local kernels. GitHub account Actions quotas apply. There is no deployment step.

DP127/128 corrections are included in this revision; the previous usb4sd1 run
used only 22 patches. Runtime audio remains opt-in. The output includes tested
storage and audio option files as documentation, not automatic system changes.

The previous usb4sd2 workflow completed compilation and module checks, but failed while uploading an empty diagnostic file. The upload fix archives empty diagnostics before publishing release assets. The old draft release remains available. No compiler cache or object tree was preserved; usb4sd3 therefore performs a clean full build, not an incremental compilation.
