Current base revision: **29 patches / usb4sd3**. An optional **43-patch / usb4sd4-egpu2** candidate appends the tested eGPU diagnostic sources through Test179; see [scope and remaining limits](consolidated/egpu179/README.md). Select `include_egpu=true` for that build. The 29 base patches and previous builds remain preserved. Full combined-kernel hardware validation is pending; reset-ACK classification changes remain excluded.

# Apple Silicon USB4 / Thunderbolt PCIe bring-up

## Consolidated full-kernel build (30 October 2026)

The current build-only integration is documented in [build/README.md](build/README.md). It combines 29 storage, PCIe/USB4, dock-display/audio and retained-power suspend patches on UbuntuAsahi commit `f7734f4c91c0f47d9e762786968057bec99a0788`, using the running Ubuntu kernel configuration. The optional eGPU extension adds 14 patches with separate provenance and source hashes. The older prototype below is retained as historical evidence.

Private development snapshot for Mac mini M1 (J274), Ubuntu Asahi, and subsequent Googlebook integration.

On 27 October 2026, the stock Linux NVMe driver enumerated a Crucial CT1000P310SSD8 behind a Yottamaster Thunderbolt 3 enclosure. Eight I/O queues and MSI-X worked. Four direct read passes (1 GiB total) returned identical SHA-256 checksums, with CRC32 matching the earlier independent diagnostic client. Primary and backup GPT signatures were verified. Controlled removal and module unload completed without reboot.

The NVMe driver itself is unchanged. The prototype supplies the missing external PCIe host, Apple DART mapping and interrupt integration. This is a constrained reference-device implementation, not yet a general hotplug driver.

## Contents

- `baseline/`: original source at Ubuntu Asahi commit `9b97d53812a6fb5c4d270899eb70a145fa762cc6`, including the complete `drivers/nvme/host` directory and relevant PCI/IOMMU files.
- `baseline-manifest.json`: exact upstream source and per-file SHA-256 hashes.
- `prototype/`: tested temporary kernel modules, DT overlay and captured platform tunables.
- `patches/`: isolated DART corrections and diagnostic source differences.
- `tests/`: bounded read-only verification program and results.
- `docs/bringup.md`: lifecycle, failure analysis and next steps.

Build the modules on the matching kernel using `make -C /lib/modules/$(uname -r)/build M="$PWD/prototype" modules`. This source subset is not a complete kernel tree. No module autoload or installation service is supplied.

## Current limits

The prototype fixes the port, ECAM addresses, bridge topology, NVMe ID, SID, MSI resource range and Apple PCIe DMA-coherency description. Direct reads and a bounded create/read-back/delete write test passed on the Crucial P310. Other devices, surprise unplug and suspend/resume remain unvalidated. Read timings include checksumming and verbose kernel logging; they do not establish maximum link throughput. A temporary workaround protects an overlay-owned PCI root node during teardown; a proper kernel-level ownership fix is still required.

The display went through poweroff and HDMI hotplug events after the test sleep inhibitor was released. Ubuntu remained reachable in the same boot. This display issue is recorded separately from the successful storage teardown.

## Licensing and provenance

Original kernel files retain their upstream licensing and notices; see `baseline/COPYING` and `baseline/LICENSES/`. Prototype code is GPL-2.0 compatible and contains kernel-derived code. Platform tunables were obtained from the local Sonoma/ADT investigation. No raw macOS firmware, account data, disk contents or full machine logs are included.

## Follow-up validation

A further 15-minute session completed three full registration/removal cycles, 1,762 paired read comparisons across distributed SSD regions, and a stock NVMe controller reset followed by fixed-range checksum verification. About 14.8 GiB was read in total. All eight I/O queue interrupts were exercised. The same Ubuntu boot remained active, and all temporary test modules were removed at the end. No data writes or mounts were performed. See `tests/validation15-results.json` and `tests/soak-read.py`.

APST was disabled; surprise unplug, suspend and generic-device support remain outside this result. Existing ACIO supplier-link warnings still need resolution before persistent integration. See `docs/generic-host-design.md` for the permanent-kernel plan.
