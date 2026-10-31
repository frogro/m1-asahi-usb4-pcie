# Reusing the previous hardware observations

The boot prototype is based on the existing open-source drivers and recorded
register traffic, not on copying macOS executable code or replaying its DMA
addresses. Existing captures were inspected again on 31 October 2026.

| Available evidence | Reusable finding | What it does not prove |
| --- | --- | --- |
| OWC lifecycle capture (20,006 events) | USB4 DART stream-enable writes at offset `0xf8`; lifecycle order | Complete power-on sequence; capture hit its event cap |
| Yottamaster lifecycle (4,209 events) | Same stream-enable offset and teardown observations | A standalone U-Boot tunnel implementation |
| Dock lifecycle (3,562 events) | Router/device removal and reappearance; DART programming | Every child behind a dock can boot |
| Direct eGPU lifecycle (3,242 events) | Host-side DART/PCIe-C ordering comparisons | NVMe boot or a general GPU firmware implementation |
| OWC/Yotta suspend captures | Quiesce traffic before sleep | Successful macOS resume; these runs did not provide it |
| Consolidated Linux DART patch 0001 | 64 streams, TTBR base `0x400`, stream enable at `0xf8`, two 32-bit SID masks, no bypass | U-Boot's allocators and device lifecycle are equivalent to Linux |

The older Linux reference snapshot still had `0xfc` as the USB4 stream-enable
base. The consolidated, hardware-tested correction and the actual captures
agree on `0xf8`. The prototype regression test first exposed the wrong offset
and then passed with that correction. Testing only the second bank at `0xfc`
would have missed the error.

The raw recordings and their hash/coverage inventory are retained in the
private work archive. Capture timestamps reflect host-side recording time;
they must not be copied into hardcoded hardware delay values. Physical addresses
and page-table values from macOS are not reusable buffer allocations.

## Work still required before a physical boot test

1. Native PCIe-C host bridge, endpoint enumeration and RID-to-SID programming.
2. ACIO/NHI firmware startup, PHY/Type-C setup, router discovery and a PCIe
   tunnel for the selected storage device. Generic PCIe NVMe alone cannot do it.
3. Correct IOMMU DMA mapping for all generic NVMe queues, identify buffers,
   PRP lists and read buffers. The current generic driver still places CPU
   addresses into those fields. The Apple internal NVMe path uses different
   SART/NVMMU machinery and must remain independently functional.
4. Bounded DART flush waits and allocation-error propagation. Existing U-Boot
   DART polling is unbounded; mapping allocation failures are not safely handled.
5. Read-only external-file hashes, clean DMA quiescence and EFI/GRUB handover.
   Then validate internal, USB and Thunderbolt boot with and without a disk.

Existing recordings narrow these tasks but do not eliminate them. No new
Sonoma capture is requested until a concrete missing sequence is identified.
The excluded Linux reset-ACK diagnostic/classification patch is not brought
back by this bootloader work.

## Concrete bring-up sequence from the open drivers

The next hardware milestone is one directly attached storage enclosure, with
an explicitly selected Mac port. Dock and display support are not prerequisites
for that first read-only storage proof.

1. Read the Type-C controller's negotiated mode, orientation and cable data.
   U-Boot's current `phy-apple-atc.c` has empty PHY operations; it does not
   configure USB4 lanes. An Apple I2C/CD321x path and the actual ATCPHY sequence
   are still required. m1n1's existing I2C/TPS6598x code and exported ATC tunables
   are useful references; its USB2 preparation alone does not establish USB4.
2. Configure ATCPHY for that negotiation **before** starting ACIO. Power domains,
   clocks and reset ordering must keep the PHY alive while ACIO is active.
3. Start the RTKit firmware and apply RC/PCIe-adapter tunables. ACIO's firmware
   shared buffers refer to its reserved SRAM window; use a bounds-checked SRAM
   mapping callback, not the default RTKit host-memory allocation path.
4. Bring up DART/NHI only after their register windows are accessible. Use
   bounded, initially polled control-ring traffic. The packet codec covers the
   wire format only; ring memory, ownership, barriers, timeouts and asynchronous
   notifications still need implementation.
5. Unlock host router ports before supplying Apple's cable-information
   capability. Discover the remote router and select PCIe adapters; allocate
   and activate the tunnel paths with valid credits.
6. Enable the PCIe-C bridge with the tested Intr2AXI ordering and **non-posted
   MMIO** semantics before probing its DART. A normal posted mapping can defer
   a fault until a later DART access. Allocate PCI bus numbers/windows and
   requester-ID/stream associations before allowing NVMe DMA.
7. Map submission/completion queues, identify buffers, PRP lists (including
   their chain pointers), and data buffers. Keep CPU cache maintenance separate
   from device-visible addresses. The current NVMe core mixes these addresses;
   replacing only its data-buffer pointer is insufficient. The internal Apple
   NVMe driver must retain its SART/NVMMU behavior.
8. Read/hash the external file, then exercise EFI block I/O and GRUB. Before OS
   handover, drain/stop DMA and establish a repeatable controller ownership
   transition. Do not claim cold boot from a retained macOS tunnel state.

These ordering requirements were checked against the local Linux reference
commit `523e0405470d74acfc7ff5d1632a2805d0559a2a` (`drivers/thunderbolt/apple.c`,
`drivers/phy/apple/atc.c`, `drivers/thunderbolt/ctl.c`, `tb_msgs.h`), alongside
our consolidated M1 PCIe-C and DART patches. That reference includes newer
platform work and is not interchangeable with our tested consolidated kernel.
The m1n1 reference is `148399585d37afa366bd0cc8f21f45c60f14e231`.

No new hardware failure is inferred from the software fault-injection tests.
They exercise failure handling needed before bringing this path to the Mac.
