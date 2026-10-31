# Test191: integrated boot initialization follow-up

The internal Ubuntu update booted `7.2.12-usb4sd4-egpu2` from release 41155087907. The installed Image/modules matched that release, the functional GRUB parameters matched the recorded successful USB boot, and the prepared m1n1 bundle matched the USB baseline. This did not reproduce complete automatic eGPU initialization.

## Two distinct initialization gaps

1. **Host probe before authorization.** The initial native host probe failed its reset-release wait at boot time 7.06 seconds. `boltd` authorized the Dynabook and Razer at 12.53 seconds. The host remained unbound. A single manual `drivers_probe` attempt enumerated the Radeon subtree. An external-root initramfs previously supplied enclosure-specific authorization/reprobe helpers; those were not generic kernel integration.
2. **Prefetch strobe before resource assignment.** Patch 43 strobes during ECAM/port initialization, before `pci_host_probe()` assigns the bridge windows. On the running 43-patch kernel all 16 sampled VRAM words were `0xffffffff`. The old scoped helper, rebuilt for the exact current configuration and symbol exports, immediately exposed real data after a late strobe. Isolated Razer tunnel reauthorization then bound all four Radeon functions and passed 1,048,576 GPU-computed values against an independent CPU calculation.

## Controlled ordering comparison

All Radeon functions were unbound and endpoint bus mastering was checked disabled before changing the root prefetch window. The helper restored every saved configuration value and did not write GPU/storage data.

- Reprogramming an already enabled window with identical values kept VRAM accessible. Thus ordinary configuration writes alone are not claimed to clear the enable.
- Strobing while the root prefetch window was disabled, then restoring the saved valid window, reproduced all-one VRAM reads.
- Strobing again after restoration recovered the same original words.
- In a separate comparison, the intentionally early/empty strobe was left unrepaired. A temporary diagnostic return probe issued the strobe when the Radeon PCI enable completed. Razer reauthorization then bound all four drivers; GPU compute passed again. The diagnostic recorded one strobe and zero missed return probes and was unloaded afterwards.

This supports moving the strobe after resource assignment. The return-probe experiment validates the later timing on the existing kernel; it is not a cold boot of the new native code.

## Appended candidates

**Patch 44** moves the native strobe into the host `enable_device` callback after successful RID-to-SID setup. It preserves the M1/kernel-owned restriction and uses the owning port mapping. It adds no GPU ID, fixed address, kernel command-line option, reset policy, or error suppression.

**Patch 45** queues a retry for an unbound host after root PCIe-tunnel activation and once after child population to cover an event racing population. It uses the existing DT host association and driver-core attachment. Queue admission is closed and work drained before child depopulation/power-off, including failed-start cleanup. The worker runs outside the Thunderbolt domain mutex, on a freezable queue. It does not authorize devices or poll periodically. The initial timeout is still reported.

Both native objects compile with the release configuration (only the local compiler executable name differs). The new candidate is `7.2.12-usb4sd4-egpu3`, comprising the unchanged original 43 patches plus these two corrections. Full Image/module compilation and a fresh native boot remain required. In particular, patch 45 needs delayed-authorization, disconnect-race and suspend validation. The installer remains pinned to the earlier release until a separate validation decision.

## Separate remaining failure

A direct AMDGPU unbind/rebind of the same PCI device produced duplicate `ip_discovery` / `mem_info_preempt_used` entries and a TTM list warning. Full Razer deauthorization/reauthorization restored GPU initialization and compute, without rebooting internal Ubuntu. The direct rebind is a failed test; patches 44–45 do not claim to fix that lifetime/cleanup path. No physical cable hotplug, new display/audio confirmation, or eGPU suspend validation was performed in this session.

The original internal boot bundle and standard Ubuntu default remain preserved. A systemd-owned hardware watchdog was enabled for these live diagnostics; diagnostic modules were removed after testing. Local raw evidence is retained separately; hashes and a sanitized result are recorded alongside this report.
