# Thunderbolt/USB4 storage boot: feasibility and first proof

The requested result is a separate Apple boot entry named `Asahi Linux`,
which retains internal and USB mass-storage boot and additionally boots a
PCIe NVMe SSD through Thunderbolt/USB4. The target OS kernel and initramfs
remain on that external SSD. The small Apple-authorized bootstrap and its
m1n1/U-Boot bundle remain internal, as required by the present Asahi chain.

This is a development objective, not a working feature. Linux recognition of
the SSD proves that the hardware can support the connection. It does not prove
that the existing U-Boot initializes it, or that Linux code can be copied into
U-Boot without adaptation. No delivery date or successful implementation is
established by this feasibility review.

## Evidence from the pinned source

Reviewed U-Boot commit: `b33034a515a068381c4aa28831fb709e91300cd1`.

- `drivers/pci/pcie_apple.c`, `apple_pcie_of_match`: the current driver matches
  `apple,pcie` and `apple,t6020-pcie`. It is not an implementation of the Apple
  USB4 PCIe-C tunnel host and connection manager used by our Linux work.
- `drivers/iommu/apple_dart.c`: DART map/unmap support exists. Its presence alone
  does not establish a working DMA path for an external PCIe NVMe endpoint.
- `drivers/nvme/nvme_pci.c`, `nvme_probe`: generic PCIe NVMe maps a BAR and enables
  bus mastering before `nvme_init`.
- `drivers/nvme/nvme.c`: queue and PRP addresses include direct casts of CPU
  pointers (`nvme_alloc_cq`, `nvme_alloc_sq`, `nvme_setup_prps`). The external
  controller's DMA address translation, including queues, PRP lists and data
  buffers, must therefore be audited explicitly. Enabling `NVME_PCI` by itself
  is not proof of DART-safe operation. Do not infer that DART bypass is safe or
  available on the target path.

## Acceptance gates

1. Bring up the selected port's power, PHY and USB4 controller with bounded
   waits; discover a directly attached, explicitly selected storage enclosure.
2. Establish its PCIe tunnel and enumerate the PCIe-C hierarchy and resource
   windows. Validate DART and DMA setup before enabling endpoint bus mastering.
3. Read a known file from that SSD in U-Boot and compare its SHA-256 with the
   Linux reference. Keep this first hardware test read-only.
4. Expose the block device through EFI services to GRUB; load its own kernel
   and matching initramfs by filesystem UUID.
5. Verify controller/DMA handover to Linux, cold/warm starts, both ports and
   missing-device timeout. Existing internal and USB boot must keep working.
6. Only then install the separate boot environment using the appropriate
   Asahi/Apple authorization flow. Preserve the existing internal fallback.

The next useful milestone is gate 3, not another menu entry. A Linux-based
intermediate loader would be a different architecture and must not be silently
substituted for the requested U-Boot approach or the requirement to keep the
target OS kernel external.

## References checked on 2026-10-31

- https://asahilinux.org/docs/alt/boot-process-guide/
- https://asahilinux.org/docs/sw/u-boot/
- https://github.com/AsahiLinux/u-boot/tree/b33034a515a068381c4aa28831fb709e91300cd1

Private backups, passwords, SSH material and machine-specific recovery data
are not part of this repository.
