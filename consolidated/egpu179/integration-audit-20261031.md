# Integrated-kernel audit, 2026-10-31

The 42-patch source replay was correct but did not reproduce all initialization performed by the diagnostic scripts. The missing PCIe prefetch-aperture enable operation is a demonstrated integration gap. Patch 43 moves that operation into the native M1 tunneled PCIe host, before downstream enumeration and after link restart. The 29 storage/display/suspend patches and 13 existing eGPU patches remain byte-for-byte unchanged.

## Controlled evidence

Hardware: M1 Mac mini, Dynabook Thunderbolt 4 dock, Razer Core X, RX 6900 XT; Yottamaster root filesystem remains on the other native Thunderbolt port. Running kernel: 7.2.12-usb4sd4-egpu1. No physical cable changes in this audit.

1. Restored the tested PCI memory reservation/reallocation command line. All GPU memory BARs were assigned; the unused I/O BAR is a separate ARM limitation.
2. Compared all 12 Sienna Cichlid firmware blobs with the previously successful internal installation: hashes match.
3. Retried AMDGPU initialization without the prefetch operation, including one scoped secondary-bus reset with all four Radeon functions unbound: PSP memory training still failed with -62.
4. Rebuilt the original Test55 diagnostic helper against the exact integrated source/configuration. Read-only observation returned all-one VRAM words.
5. Enabled PREFMEM_ENABLE through this explicitly scoped helper: VRAM immediately became readable. A direct GPU retry still failed because the earlier failed initialization had left device state behind.
6. With Radeon functions unbound, deauthorized and reauthorized only the Razer Thunderbolt device. GPU initialization then completed; all four drivers bound. IB tests and repeated deterministic Vulkan compute over 1,048,576 values passed.
7. Two further complete software deauthorization/reauthorization cycles with all four drivers initially bound passed. Each cycle included a 1 GiB direct read of the Yotta device and successful GPU compute after reauthorization. No reboot or Oops occurred. Removal still logged SMU/gfxoff and, in one cycle, JPEG/VCN power-gating timeouts; these diagnostics are not declared fixed.
8. Compiled the native host implementation and replayed all 43 patches on a second fresh full-source checkout. Native-hook cold boot and physical hotplug remain pending; this audit does not substitute the helper result for that test.

## Runtime prerequisites and remaining gaps

| Area | Consolidation result | Limit / follow-up |
| --- | --- | --- |
| USB4 / PCIe / NVMe, patches 1–26 | Existing source hashes and full replay retained | External-root boot still uses local initramfs authorization/reprobe hooks; see below |
| Suspend, patches 27–29 | Automatic retained-power s2idle implementation retained; no UART/watchdog patch | Historical tests155/157 passed; complete integrated system with eGPU suspend not validated |
| AMDGPU / TTM / HDA / I2C / xHCI, patches 30–42 | Tested source hashes preserved | Physical unplug during initial failed probe is a distinct unresolved error path |
| M1 PCIe prefetch aperture, patch43 | Newly integrated before enumeration and after link restart | Native object compile and replay passed; fresh kernel boot pending |
| PCI resource reservation | Tested arguments exported with artifacts | Bootloader must actually supply them; kernel patches do not alter defaults |
| AMDGPU runpm/aspm/rebar | Tested module parameters documented | These remain deployment parameters, not silently changed driver defaults |
| Radeon I2C runtime PM | Earlier physical-removal tests held this controller awake | Current compute works with power/control=auto; this does not establish equivalent USB-C hotplug coverage |
| Dock display/audio | Native static DT and automatic connection patches retained | Earlier physical output/audio tests remain evidence; no dock display cable test during this unattended audit |
| AVD firmware | Corrected firmware build/packaging already included | Prior hardware decode validation retained; firmware is not part of Linux source patch count |
| Native HDMI after desktop idle/wake | Text console recovery known | Graphical idle/wake failure remains separate and unresolved |
| Application recovery | Compute and controlled rebind validated | A process losing its GPU may need restart; transparent application recovery is not claimed |

### External-root initramfs hooks

The current Yotta installation contains a local dracut module that authorizes the known Ash Creek enclosure and retries an initially unbound PCIe host after authorization. It also restores the previous boot selection for fallback. These installation-specific scripts are not supplied by the 43 Linux patches. They remain necessary for the demonstrated external-root setup until a generic boot path is validated. Do not ship a machine-specific boot blob or UUID-based authorization script as a general kernel fix.

### Module and configuration integrity

The prepared configuration retains all 12,501 previously enabled options; only release metadata and the added PCIe host option differ. All four Radeon functions use MSI interrupts after initialization, despite legacy `of_irq_parse_pci` warnings. The global TTM diagnostic parameter is absent. All 8,626 installed module, Image and board-DTB files match the previous successful GitHub release archive byte-for-byte. The read-only `build/check-runtime-prerequisites.py` inventories the actual command line, module parameters, BAR mapping attributes and driver bindings; it never writes sysfs or resets hardware.

### Initial-probe disconnect

A previous recording captured removal of the entire dock while Radeon initialization was still running. Error unwinding reached VCN software cleanup after hardware resources had been released, causing an Oops. The established surprise-removal guards cover the tested initialized-device removal paths; they do not establish safety for every failed-probe cleanup path. Patch43 addresses the demonstrated initialization prerequisite, not this separate concurrency defect.

### Additional controlled observations

A connected AMDGPU unbind completed in 0.203 seconds; rebind completed in 23.622 seconds and compute passed. Native Asahi remains loaded and Vulkan enumerates Apple M1 through Honeykrisp. No failed systemd units were present at the end of these checks.

A UCSI child-driver rebind after GPU initialization completed without a command timeout, but did not activate the USB-C partner's DP alternate mode; all Radeon display connectors remained disconnected. No visual output is claimed for this unattended audit. The operation emitted one DART fault (`0x83000402`, stream3, address0). The identical fault is present immediately after UCSI/I2C unbind in historical Test179 and Test190 logs. GPU compute and Yotta reads still passed afterwards. This remains an unresolved teardown observation, not a newly proven regression or a reason to install a blanket USB reset.

The historical overlay helper only applied the diagnostic DT; native static DT patches replace it. The historical TTM scope helper operated on synthetic structures and did not touch hardware. Neither is an omitted runtime initialization like the Test55 prefetch strobe.

The installed internal boot-arm helper had a stale initramfs hash. Its expected metadata was updated from the verified booted Yotta files, with a backup, and it gained a check-only option. It still requires the SanDisk and checks its actual file hashes before arming. The SanDisk was absent, so its current contents were not reverified. The original m1n1 boot blob hash and empty GRUB next_entry were unchanged. No kernel was copied internally and no reboot was armed.

### Deliberately excluded

No ACK-timeout suppression/classification patch, speculative USB-C reset policy, global TTM override, or unvalidated UART change is added. Native-host integration is scoped to M1 kernel-initialized tunnels and uses the driver's mapped registers. Existing build artifacts and kernels remain available.

## Recovery during unattended checks

During active tests, an Apple hardware watchdog with a renewable lease protected the system. Afterwards ownership was handed to systemd PID1 and verified, with 30-second runtime/reboot watchdog settings for this boot and panic reboot enabled; no expiring test lease remains active. The verified original internal Ubuntu boot selection remains the fallback. The Yotta root controller is never unbound. No system sleep or physical-disconnect test is performed while the operator is away.
