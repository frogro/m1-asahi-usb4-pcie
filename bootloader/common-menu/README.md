# Common internal GRUB menu

Apply `0001-common-internal-menu.patch` after the USB4-child source profile.
This is an opt-in policy change, not a change to controller setup, tunnel
programming, kernel parameters or ExitBootServices teardown.

The previous installed DT selected the WD ESP before GRUB. Consequently an
attached Ubuntu SSD could not reach the OS menu when the WD was absent.

With `u-boot,common-menu` on `/config`, complete healthy external discovery
is followed by the existing verified internal ESP loader. That loader validates
`fw_dev_part`, the native Apple NVMe driver and `u-boot,recovery-partuuid`, then
uses the shared EFI handoff with all discovered block devices registered.
Zero, one, or several external boot candidates do not choose an OS. GRUB does.

Remove `u-boot,boot-partuuid` and `u-boot,preferred-partuuid` from this profile.
An explicit environment target conflicts with common-menu mode and is rejected.
Keep the installation-specific internal `u-boot,recovery-partuuid` and the
identity-checked `u-boot,local-bootcmd` for the no-TB/USB4-link USB/internal path.
Do not copy another installation's internal ESP UUID. Inventory-only diagnostics
cannot enable common-menu handoff. Failed/incomplete scans still stop safely.

The common internal GRUB EFI must load the installation's menu. Menu entries
search OS filesystems by UUID, not enumerated USB/NVMe numbers. An absent OS
medium cannot boot; the menu itself no longer depends on that medium. Cloned
filesystems with duplicate UUIDs require separate identities.

Validation: 74 extracted actual orchestration cases under ASan/UBSan and an
Apple M1 build passed. See validation.json for hardware results when available.
The test includes missing/multiple media, USB/NVMe discovery, failures on both
ports, strict target conflicts, and existing explicit recovery behavior.

Run `python3 test-scan.py PATCHED_SOURCE OUTPUT_DIRECTORY`.
The existing usb4-child build/patch series remains unchanged. This additional
profile has not been promoted to CI default or published. No full Android image
is built here.

## Integration update — 5 November

This directory is now included in the runtime integration branch. The common-menu
profile has a complete pinned build recipe and CI checks; older hardware notes
above are historical stages, not the final combined result. See
`docs/runtime-integration-20261105.md` at the repository root for current status.
