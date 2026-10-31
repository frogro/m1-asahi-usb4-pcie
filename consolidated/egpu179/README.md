# Experimental eGPU integration after Test179

This extension appends 13 patches to the unchanged 29-patch USB4/storage/dock/suspend series on UbuntuAsahi commit `f7734f4c91c0f47d9e762786968057bec99a0788`. The combined build is `7.2.12-usb4sd4-egpu1`. Select `include_egpu=true` in the existing build-only workflow. The default build remains the 29-patch usb4sd3 variant.

This is a reproducible diagnostic source snapshot, not a completed upstream submission or an installed kernel. Original test markers are intentionally retained to match the built/tested sources. Source and patch hashes are checked before and after application. Original Joshua Warren commits imported from linux-aurora PR188 retain authorship, commit text and sign-offs; adaptations are identified separately. Development was AI-assisted. See PROVENANCE.txt.

## Included

- Non-posted AMDGPU MMIO, VRAM and firmware-buffer handling, CPU-visible BO placement and GFX10 queue staging.
- TTM mapping policy derived from the owning PCI BAR, without the old global override or public structure-layout changes.
- PCI-disconnect guards for HDA, AMD DesignWare I2C, xHCI and AMDGPU.
- Offline graphics event retirement, stream cleanup, HIQ handling and HDCP reference cleanup.
- Test179 per-adapter I2C transfer guard: UCSI unregister commands return ENODEV once the AMD PCI function is marked disconnected.

## Evidence and limits

The successful diagnostic boot also used `pci=hpbussize=16,hpmmiosize=32M,hpmmioprefsize=512M,realloc=on`. This replaces the storage-only `pci=hpbussize=16` argument; it is not automatically supplied by the driver patches. See [tested-egpu-boot-parameters.txt](tested-egpu-boot-parameters.txt), exported with eGPU build artifacts. The first integrated Yotta boot omitted the memory reservation/reallocation options and failed Radeon memory BAR allocation with probe error -12. Restoring the tested options requires a fresh hardware check; it does not yet explain the subsequent dock link loss.

Matched diagnostic modules on M1 + RX 6900 XT have passed GPU compute, DP/HDMI/USB-C output, two-monitor combinations and audio tests. Test179 survived two complete Thunderbolt removals while USB-C output was active, with all four Radeon drivers bound. Reconnection rebound all drivers, GPU compute passed, and the user confirmed both Mac-HDMI and Radeon-USB-C pictures. Independent Yottamaster 1 GiB read checksums remained correct. During these physical removals the Radeon I2C controller was held awake, matching the earlier failing case.

These observations do not certify the entire integrated kernel. Its full build and hardware boot must be reported separately. The transfer guard does not protect a transaction already in flight or accesses before the PCI-disconnected flag is set. USB-C display-cable reconnection has been inconsistent; a UCSI PPM initialization timeout occurred after the first eGPU reconnect, and one offline display teardown emitted a DMCUB diagnostic. These are not silently suppressed or declared fixed.

The diagnostic tests loaded AMDGPU with `runpm=0 aspm=0 rebar=0` and enabled native Mac HDMI audio using `appledrm.hdmi_audio=1`. This snapshot does not change those driver defaults. It does not validate eGPU suspend, active Radeon PCM-stream removal, all applications, other GPU families or removal before the PCI core marks the device disconnected. Applications such as vkcube are restarted after device loss; transparent application recovery is not claimed.

The original diagnostic initialization also issued a separately scoped PCIe PREFMEM_ENABLE strobe using the Test55 helper. That hardware-specific helper is not included as an automatically executed action. Its necessity and the appropriate native host implementation must be checked during integrated-kernel testing before claiming a standalone eGPU setup. No physical address or device-ID-specific strobe is inserted into a generic driver here.

No ACK-timeout classification patch, firmware replacement, kernel installation, boot-default change or automatic deployment is included. Existing kernels and the prior successful GitHub build remain intact. The GitHub runner has no saved object cache, so this is a clean build rather than an incremental compilation.
