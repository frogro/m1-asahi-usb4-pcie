# Googlebook boot-storage path guard candidate

Android USB4 policy may deauthorize PCIe routers during startup. The selected external root needs its router and every live ancestor to remain authorized. The earlier local UUID guard protected only the sysfs target; deauthorizing a parent recursively removed the protected child without re-entering that check.

This opt-in patch resolves `boot_protect_uuid` in the same Thunderbolt domain under its topology lock, holds the returned reference, and walks the live parent chain. It returns EBUSY before any recursive deauthorization when the target belongs to that path. It does not authorize devices, bypass SELinux, or change unrelated branches. The UUID must identify the actual authorized boot router; selecting it generically from the root device remains initramfs integration work. It contains no dock/enclosure chipset allowlist.

The patch is standalone against the unmodified switch.c in the Googlebook source; do not stack it on top of the older leaf-only guard. It is not yet part of the default CI patch list. Full kernel release builds should use their normal symbol/dependency validation. The local diagnostic module was checked against the shipped module (same imports, exports and vermagic; old implementation machine code reproduced) because the old complete Module.symvers was unavailable locally.

Run `python3 test-ancestors.py PATH_TO_PATCHED_SWITCH_C NEW_OUTPUT_DIRECTORY` for the extracted-C ASan/UBSan topology tests. Hardware results are in validation.json. The unchanged direct Mac control passed. The modified dock test reached Android boot_completed and a user-confirmed responsive GUI. Logs show both parent route1 and selected child route301 deauthorization blocked. The independent read test was not completed because ADB stopped responding; it is not claimed as passed. No production image or default boot entry is changed by this repository directory.

Local regular integration on 2026-11-04: Fanxiang-selected initramfs and matching USB4-child U-Boot installed and remount/hash verified. Kernel Image unchanged; 600s diagnostic timer removed; old Yotta initrd retained. Regular initrd SHA256: `14bb69283f62e974be78fc7ac816cc108fa034fa5c5a6a21d1739883ed962714`. No additional regular reboot has been performed. Full image remains local.

## Integration update — 5 November

This directory is now included in the runtime integration branch. The common-menu
profile has a complete pinned build recipe and CI checks; older hardware notes
above are historical stages, not the final combined result. See
`docs/runtime-integration-20261105.md` at the repository root for current status.
