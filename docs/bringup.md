# Bring-up record

## Integration

The controller mapping uses non-posted MMIO where required. Platform fabric/reset/clock initialization precedes tunnel authorization. Linux scans the test host, assigns BAR windows, and obtains a translated DART DMA domain. The enable callback checks the actual private DART stream bitmap (SID 1), rather than assuming `iommu_fwspec` contains IDs: Apple DART stores its stream mapping privately. RID 0x0300 maps to SID 1. The MSI parent provides 32 AIC-backed vectors; NVMe used one admin and eight I/O vectors. Linux allocated a 64 MiB host memory buffer.

No macOS physical DMA addresses are replayed. Captures supplied register meaning and initialization order; Linux owns the current mappings and buffers.

## Corrections

1. Correct the USB4 DART stream-enable base and split a 64-bit SID mask into two 32-bit registers. Earlier tests exercised SIDs 1 and 33; stock NVMe currently uses SID 1.
2. Validate the real DART stream assignment before enabling endpoint DMA.
3. Keep the temporary host/module alive while registered; separate stop, remove and resource release for diagnosis.
4. Preserve ownership of the overlay-provided root node during PCI stop.

The fourth issue caused the repeated loss of the machine in previous teardown tests. This kernel's `of_pci_remove_host_bridge_node()` interprets `OF_DYNAMIC` as proof that PCI created the node and uses `np->data` as a changeset. Our overlay node is dynamic but has NULL `np->data`. The local workaround temporarily hides this exact root node from the PCI node-removal helper, then restores the reference for normal bus release. It does not globally clear OF flags.

A matching upstream proposal is Hervé Codina's [v12 10/10: PCI: of: Avoid np->data usage for the node changeset](https://lkml.rescloud.iu.edu/2610.0/01519.html). The proper integration should track PCI-owned changesets in PCI objects rather than infer ownership from OF_DYNAMIC. The current module workaround is not that full kernel fix.

## Successful lifecycle

After recovery, round 5 (no NVMe binding) passed all three teardown phases and module unload. Round 6 enabled stock NVMe binding, identified the namespace, verified 1 GiB of direct reads, then passed all three phases and full cleanup. A later general direct-I/O test exposed a missing `dma-coherent` property in the synthetic PCIe root; the resulting SWIOTLB growth exhausted memory. With the property restored to match Apple's native PCIe node, a full 200 MiB direct read and bounded 4 MiB create/read-back/delete FAT write test passed with zero SWIOTLB use. Udisks and the udev execution queue were restored, temporary modules removed, and the tunnel deauthorized.

Setup sequence used: hold sleep/idle, stop automatic mounts and udev execution, enable netconsole, load host with binding disabled or enabled, run host stages 1–6, authorize tunnel, stages 7–10, load isolated DART and overlay, register host. Set the resulting external namespace read-only before any test. Teardown writes 1, then 2, then 3 to the `teardown` attribute, checking each result; only then remove overlay, DART, restore routes, deauthorize tunnel and remove controller. Do not use `host=0` as a shortcut while registered.

## Next generic implementation

- Backport the PCI OF ownership fix and replace the diagnostic workaround.
- Discover port resources and tunables from the Apple device tree; remove fixed addresses.
- Enumerate arbitrary downstream PCI bridges/endpoints; allocate bus and BAR resources normally.
- Allocate RID/SID mappings and MSI resources dynamically with bounds checking.
- Integrate tunnel authorization, device removal, lifetime and power management with the existing USB4/PCI frameworks.
- Repeat read verification after controlled reconnection, then test other enclosures/endpoints. Add surprise-unplug, suspend and separate explicitly authorized write tests later.

The private repository is a source and evidence snapshot, not a ready-to-install generic driver release.

## Patch artifacts

`0001` is the focused two-fix patch against the pinned baseline. `0002` is a cumulative baseline-to-diagnostic-module diff, including those fixes, logging, private SID validation and test-only compatible matching. These are alternative views, not a sequential patch series. The PCI host implementation is in `prototype/apple_apciec_step.c`; stock `drivers/nvme/host/pci.c` has no patch.
