# USB4 child-router development profile

This profile extends the automatic transport bootloader to configure a USB4 v1 router downstream of a USB4 dock. It builds on the separate USB3 recovery profile. It is not the published/default bootloader.

The original downstream path supported a TB3 child only. It rejected the USB4 header before EFI media discovery. The new path preserves legacy TB3 handling, programs the USB4 CM version, checks router-ready/configuration-ready, discovers adapters, queries both routers' PCIe buffer limits, and uses the USB4 path planner for the second link. Router routes, adapters and resources are discovered; no enclosure vendor/product whitelist is added.

PCIe capability headers are read one DWORD at a time. Reading two words at the Fanxiang PCIe adapter's capability returned an address error because the second word is not implemented. Lane state is read separately when required.

Validation on 2026-11-04:

- Configuration-only hardware run passed for Mac → Dynabook → Fanxiang (USB4), route 0x301, PCIe-up adapter 3.
- Automatic inventory passed: both PCIe tunnel links, native WD SN730 identify, MBR/GPT read, and correct WD EFI selection. SanDisk USB storage behind the dock was also discovered. No disk writes or OS handoff in that run.
- Full Googlebook boot FAILED: the user corrected the initial GUI observation; it crashed before the interface appeared. The unchanged repeat also failed after logo/mouse. Both boots reached native NVMe root; the repeat captured NVMe and EXT4 I/O errors at 49.6s, including PCIe-hotplug-thread eviction. macOS returned and boot files were restored and remount-verified. Historical direct-path diagnosis identified Android USB4 deauthorization; its existing boot-router guard protects only the selected enclosure, explicitly not ancestors. Parent-dock deauthorization is a strong hypothesis for this failure, but the current caller has not been captured. The pre-GRUB NVMe inventory success remains separately verified.
- Extracted-source tests cover 127 router configuration cases, 324 register-write guard cases, 186 nested path/fault cases, and 516166 event-source boundary cases, using ASan/UBSan. USB3 regression tests are also run by build.py.
- A clean build reconstructs the exact changed source from the pinned upstream commit and hashed patch series. Rebuild binary timestamps differ from hardware-test artifacts; the clean rebuilt binary is not independently hardware-tested.

Limits: USB4 v1, one external parent plus one child router, unique connected storage branch. Deeper chains, multiple simultaneous downstream branches, USB4 v2 and eGPU coexistence are not qualified by these runs. USB3 repetition and full default-menu integration remain separate qualification steps.

Run `python3 build.py PATH_TO_UPSTREAM_GIT_CHECKOUT NEW_OUTPUT_DIRECTORY --jobs 4`. The script builds and tests locally; it does not install or publish. Complete Googlebook images remain local.

## Integration update — 5 November

This directory is now included in the runtime integration branch. The common-menu
profile has a complete pinned build recipe and CI checks; older hardware notes
above are historical stages, not the final combined result. See
`docs/runtime-integration-20261105.md` at the repository root for current status.
