# Radeon follow-up candidate rc2

These three-file changes follow the successful rc1 boot/display/eGPU test on
10 November 2026. They do not change the PCIe reset timeout or hide diagnostics.
The original rc1 integration and hashes remain reproducible. `apply.py` requires
its exact Git tree and checks patch, preimage and postimage hashes.

## Memory statistics

Eric Huang's upstream proposal, [drm/amdgpu: fix vm->stats leak from stale
bo_memtype on preferred_domains change](https://www.mail-archive.com/amd-gfx@lists.freedesktop.org/msg155275.html),
identifies why recomputing the preferred placement when subtracting a BO can debit
a different bucket from the original addition. This adaptation caches that bucket.
It also uses the cached bucket for shared/private transfers and caches the
original eviction charge, because both also depend on mutable preferred_domains.
A BO move still subtracts the old charge and records a fresh one. This corrects
accounting; it is not evidence of a physical VRAM allocation leak.

The caching approach derives from that proposal; the sharing/eviction extensions
and tests are local changes. AI assistance was used. No upstream acceptance,
third-party endorsement or new DCO sign-off is claimed.

## Disconnected display teardown

The existing local PCI removal path sets `adev->no_hw_access` before unloading a
surprise-removed Radeon. The newer Asahi display teardown still calls the ISM
full-power transition after stopping its workers. Skip that hardware transition
when no_hw_access is set. Worker cancellation and software destruction remain
unconditional; cancellation stays outside dc_lock. Connected teardown is unchanged.

This eliminates one inappropriate hardware request observed in code review.
The hot-unplug log has a DMCUB diagnostic, but no caller stack proving this was its
only source. Do not claim that all DMCUB failures or all unplug races are fixed.

## Validation and limits

`test-regressions.py` compiles the actual before/after VM functions and DM teardown
sequence with host stubs and undefined-behavior sanitization. It exercises 3,920
CPU/GTT/VRAM combinations: preferred-domain changes, no/valid/invalid residency,
shared/private transfers, moves, discardable BOs and a BO accounted to two VMs.
It also checks connected versus offline teardown ordering. The old code must fail
the regression conditions and the patched code must pass. This is not a GPU,
concurrency, full-kernel or power-loss test.

CI must compile the AMDGPU/display objects and complete Image/modules/DTBs before
an rc2 package can be tested. Rebuild a matching initramfs and keep the tested
7.2.12 boot path available. Recheck VM-fini warnings under Vulkan use and the full
Razer disconnect/reconnect, dock display and dual-monitor sequence on hardware.
PCIe-C startup -110 remains an independently tracked readiness issue.
