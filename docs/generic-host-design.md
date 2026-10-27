# Generic host integration: source review

This is a design record; it does not claim that the fixed prototype is generic.

The pinned `pcie-apple.c` already provides useful patterns: `apple_pcie_enable_device()` obtains the RID from `pci_dev_id()`, maps it through `of_map_iommu_id()`, allocates a RID/SID table slot from a bitmap and writes the mapping. `apple_pcie_disable_device()` releases the matching slot. MSI allocation obtains vectors from a bitmap and the parent AIC domain. These patterns can guide the external-host driver, but external tunnel lifecycle and its DART are different from the internal host.

The current prototype permits only four config-space BDFs, fixes bus 3/devfn 0 and c0a9:5427 in the DMA guard, programs RID 0x0300/SID 1, reserves a fixed BAR window and AIC interrupt range. The overlay supplies a single iommu-map entry. The hardware link and source evidence do not justify removing these guards without implementing resource discovery and DMA isolation first.

Required sequence for generic support:

1. Describe the external host/DART/interrupt/power resources in device tree using kernel bindings. Discover port resources instead of baking in this machine's addresses and phandles.
2. Replace the BDF allowlist with safe ECAM mapping, link-state gating and normal bridge enumeration. Handle absent devices and link loss without issuing unsafe MMIO accesses.
3. Provide an IOMMU mapping strategy before endpoint probe; dynamically allocate and release RID/SID entries while preserving isolation. DT iommu-map and hardware table size need to agree; a hardcoded single entry is insufficient.
4. Allocate bridge windows, MSI vectors and host resources from platform data; keep DMA guarded until the mapping is validated.
5. Coordinate the external host lifetime with USB4 tunnel creation/removal. Quiesce endpoint drivers and DMA before disabling the tunnel. Do not equate software deauthorization tests with physical surprise unplug coverage.
6. Replace the diagnostic OF-node ownership workaround with the reviewed PCI-core fix, then build a separate bootable test kernel with the existing kernel retained as a fallback.

The NVMe controller reset test uses the kernel's `reset_controller` sysfs attribute. Its implementation calls `nvme_reset_ctrl_sync()`; the PCI driver disables a live controller, synchronizes queues, re-enables it and recreates admin/I/O queues. This exercises DMA and interrupt lifecycle without a whole-machine reboot or a filesystem write.

## Permanent kernel versus current live test

Current live test: out-of-tree host, DART and overlay modules compiled for the installed Ubuntu kernel; no /boot replacement or autoload configuration. The stock NVMe driver remains unchanged. Controlled teardown removes all test modules.

Permanent PCI-core fix: the upstream ownership proposal changes `drivers/pci/of.c` and `include/linux/pci.h`, adding changeset ownership to PCI structures. This requires a matching kernel and modules build. The cited v12 patch is the last item of a series and its context includes earlier fw_devlink changes that are absent from the pinned Ubuntu baseline. Do not apply the whole series blindly or treat a successful textual apply as runtime validation. Review the required subset/backport, build a separate kernel package, retain the existing boot entry, and repeat lifecycle tests without the local node-hiding workaround.

Reference: https://lkml.rescloud.iu.edu/2610.0/01519.html

## Validation scope

The 15-minute follow-up retains the same compiled module binaries. Only stale source comments and documentation were corrected. Repeated bind/read/unbind cycles test that DMA domains, MSI allocations and host registration can be reacquired. Parallel readers are pinned one per CPU to exercise all eight NVMe I/O queue interrupts. Reads use O_DIRECT and paired SHA-256 comparisons at rotating disk offsets; a post-reset fixed-range read also matches the earlier independent diagnostic CRC32. Normal NVMe APST remains disabled during these tests, so a successful result does not establish low-power-state stability.

Two known supplier-link warnings recur when the runtime overlay is attached: the inactive/other ACIO node's IOMMU and NHI suppliers under `/soc/cio@381ac0000`. They were also seen in earlier direct-DMA tests. The current read test passes despite them; persistent integration still needs correct OF/fw_devlink ownership and dependency handling. No claim is made that the entire kernel log is warning-free.
