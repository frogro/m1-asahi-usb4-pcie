# Consolidated kernel build — no installation

This workflow builds a complete ARM64 `Image`, all modules selected by the running Mac kernel configuration, and DTBs. It runs on a hosted Ubuntu 26.04 ARM64 runner. Nothing connects to the Mac or changes installed kernels, modules, firmware, bootloader or boot defaults.

## Inputs

- UbuntuAsahi/linux commit `f7734f4c91c0f47d9e762786968057bec99a0788` (Linux 7.2.12).
- `running-kernel.config`: read from `/boot/config-7.2.0-1001-asahi-arm` on 30 October 2026.
- 22 patches in `consolidated/20261030`, including storage/PCIe/USB4 and dock video. Preimage, patch and final file hashes are checked against the real Git base before compiling.
- The incomplete AMDGPU/TTM/eGPU modifications are excluded. Stock AMDGPU and TTM remain enabled as configured by Ubuntu.

The new release is `7.2.12-usb4sd1`. Existing enabled options must remain unchanged after `olddefconfig`; changes to compiler metadata and release identification are reported separately. `PCIE_APPLE_PCIEC=y` is added. Public Ubuntu trust/revocation certificates are assembled using the source packaging rules. Modules are signed with a newly generated build key, not Canonical's private key. The private signing key is not exported.

## Outputs

The workflow stores results as assets of a draft release in this private repository. It does not use Actions artifact or cache storage. Files exceeding the release asset limit are split into numbered `.partNNN` pieces; concatenate them in numeric order before extraction.

- `linux-7.2.12-usb4sd1-arm64.tar.zst`: kernel Image, System.map, configuration, DTBs and all matching staged modules, with module debug symbols stripped and BTF retained.
- Compressed `vmlinux` with the configured debug information.
- Configuration comparison, module list/vermagic, Module.symvers, public signing certificate, applied commit metadata, build log and SHA-256 hashes.

The archive is not an installer and contains no initramfs or modified m1n1 boot image. A later installation must separately prepare a matching initramfs and the existing Asahi boot pipeline, keep all current kernels, and use an explicit additional boot entry. Firmware is unchanged and comes from the existing Ubuntu installation.

Suspend remains intentionally guarded. Reset ACK semantics and combined hardware validation remain open. A passing build does not certify hardware stability. The consolidated patches preserve source attribution; no upstream PR is created by this workflow.

## Running

Start **Consolidated M1 kernel (build only)** with `workflow_dispatch`. The workflow uses standard hosted ARM64 resources, at most one concurrent job, and a six-hour timeout. It checks free storage before building and does not remove any user data or local kernels. GitHub account Actions quotas apply. There is no deployment step.
