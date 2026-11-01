# First native USB4 EFI and external-root boot, 2026-11-01

The J274 M1 booted the Samsung 970 EVO Plus in the Fanxiang MP400 through native USB4. U-Boot read the external EFI image; GRUB loaded the external kernel and initramfs; Linux mounted `/dev/nvme1n1p3`. This is a bounded diagnostic success, not yet a production USB4 bootloader release.

The first complete attempt failed after GRUB. Control v17 read and hashed all 1,560,576 bytes of the EFI image successfully. Instrumented v18 then proved that Linux had started but the MP400 router remained `authorized=0` under `security=user`. The existing initramfs contained a root-authorization hook restricted to the old Intel Ash Creek Yottamaster enclosure.

Comparison v19 retained exactly the v18 U-Boot binary and the existing egpu3 kernel. Only a diagnostic initramfs extension was added to authorize the selected MP400, guarded by root UUID, router vendor/device, unique ID, physical host port, and an explicit command-line opt-in. The external root mounted at 8.65 seconds. SSH, two matching direct 64 MiB reads, dock discovery, and all four Radeon driver bindings passed. No failed systemd units were reported. Reset-release timeouts and IRQ parsing warnings remain recorded separately; this is not a claim that all kernel issues are fixed.

`diagnostic-only.patch` applies to the integrated ten-patch U-Boot tree. It contains forced diagnostic entry, logging, stop-before-EFI controls and reset behavior. **Do not install this patch wholesale as the normal bootloader.** The unchanged m1n1 release binary was used; its source was not accessed. The production manifest and kernel series were not changed.

The next integration must extract the USB4 router/path changes into the full bootloader, retain the existing internal/USB/TB3 paths, and select transport from validated cable/router state. Linux root authorization belongs in the selected installation's initramfs. A production installer should generate an allowlist for the selected root enclosure rather than hard-code this one MP400 or authorize every attached PCIe device.

Build scripts depend on the preserved local diagnostic DT and integrated U-Boot tree. `test-efi-snapshot-v16.py` tests the exact snapshot function with ASan/UBSan; `test-initrd-authorize-v19.py` checks the authorization guards. Earlier router/path tests remain in the sibling `usb4-mp400-20261101` directory. Full observations, candidate hashes, and cleanup state are in `result.json`.

The five-minute return timer initially failed because the generated diagnostic Python helper contained an invalid string literal. This was a test-harness error. The helper and generator were corrected, the embedded script was syntax-checked, and the return service was explicitly restarted over the working SSH connection. The original external GRUB menu was restored byte-for-byte; the normal integrated bootloader had already been restored at Linux startup. Final return status is recorded in `result.json`.
