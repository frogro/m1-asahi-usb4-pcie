# Apple Silicon USB4 / Thunderbolt PCIe bring-up

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

The prototype fixes the port, ECAM addresses, bridge topology, NVMe ID, SID and MSI resource range. Other devices, surprise unplug, suspend/resume and writes have not been validated. Read timings include Python checksumming and verbose kernel logging; they do not establish maximum link throughput. A temporary workaround protects an overlay-owned PCI root node during teardown; a proper kernel-level ownership fix is still required.

The display went through poweroff and HDMI hotplug events after the test sleep inhibitor was released. Ubuntu remained reachable in the same boot. This display issue is recorded separately from the successful storage teardown.

## Licensing and provenance

Original kernel files retain their upstream licensing and notices; see `baseline/COPYING` and `baseline/LICENSES/`. Prototype code is GPL-2.0 compatible and contains kernel-derived code. Platform tunables were obtained from the local Sonoma/ADT investigation. No raw macOS firmware, account data, disk contents or full machine logs are included.
