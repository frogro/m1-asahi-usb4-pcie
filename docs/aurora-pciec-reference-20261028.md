# Aurora PCIe-C reference comparison

This note records a development implementation discovered after the local M1
Mac mini APCIEC prototype and ATC fallback tests. The source is the third-party
`linux-aurora` integration tree, not mainline Linux or the public Asahi branch.
It is useful engineering evidence, but every change still requires local build
and hardware validation.

## Why it is relevant

The tree contains a complete cable-lifetime model for Apple PCIe-C hosts:

- ACIO creates the PCIe host only after the USB4 router and NHI are live;
- unplug removes the PCI host before ACIO and its power domains disappear;
- T8103 PCIe-C, DART, MSI, root-port resources, and tunables are described in
  the device tree;
- tunnel MMIO uses completion barriers after relaxed accesses;
- reset, LTSSM, interrupt, bus scan, suspend, and restore paths are explicit.

The completion-barrier rule independently matches the local macOS-derived
prototype fix: non-posted APCIEC accesses require `mb()` and `isb()` to avoid a
later asynchronous SError.

## Seed commits used by test3

The isolated `7.2.12-usb4-pciec-test3` source uses these commits as a seed:

| Commit | Purpose |
| --- | --- |
| `56ecc44554c7` | Cable-powered PCIe-C root-complex lifecycle |
| `40f2afe0aefd` | T8103-family PCIe-C controller support |
| `e32f89d3db2d` | Live tunnel access, teardown, and MMIO completion barriers |
| `8904429ab5cc` | Populate the tunneled PCIe host under ACIO |
| `6243e9d63a90` | T8103/T8112 PCIe-C device-tree nodes |
| `86665d66e67e` | Connect PCIe-C power and router resources |
| `e08681891d79` | T8103 enumeration resources and tunables |
| `79e9d853b0fb` | T8103 tunnel restore-state description |

Only the T8103/M1 portions are retained in the local integration. Partial
T600x/T602x changes are excluded.

## Deliberately excluded from the first NVMe test

The later eGPU pull request adds identity large-BAR windows, non-posted AMD GPU
BAR access helpers, non-coherent GTT handling, delayed downstream-slot scans,
and root-port prefetchable-window setup. These prove that PCIe tunnelling can
support much more than NVMe, but they are not prerequisites for the first M1
Mac mini NVMe test and are therefore excluded from test3.

Exact source patches and their checksums are preserved under `patches/pciec-test3/`.

References:

- `https://github.com/omacom/linux-aurora/pull/188`
- `https://github.com/joshuaswarren/linux-aurora/tree/egpu-nonposted-bars`
- `https://lore.kernel.org/asahi/20260906-b4-apple-soc-tbt-v2-0-1f80085f93fb@kernel.org/`
