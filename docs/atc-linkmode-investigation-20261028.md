# Apple Silicon USB4 ATC and link-mode investigation

## Scope

This note separates three failures that can otherwise look like one problem:

1. the initial USB4/Thunderbolt link loss,
2. the subsequent USB4-to-native-USB fallback warning in `atcphy_mux_set()`, and
3. the missing Apple PCIe host path needed for an NVMe device to appear as a normal Linux PCIe/NVMe device.

The stable Ubuntu kernel remains the default boot target. Experimental kernels use separate boot entries.

## Reproduced sequence

With an ASM2464 NVMe enclosure attached, Linux first trains both lanes, discovers the remote USB4 router, and configures the control path. Roughly ten seconds later the ACIO firmware reports link errors 83, 84, 87, and 89 followed by `SBX disconnected`. The Type-C controller then changes from USB4 to native USB without changing the logical USB role (`HOST` to `HOST`). Because the existing TIPD code only quiesces DWC3 when the role changes or a disconnect is reported, ATCPHY still sees its PIPE handler active and emits the warning at `drivers/phy/apple/atc.c`.

The warning is therefore a fallback-transition defect. It occurs after the initial high-speed link loss and is not evidence that ATCPHY caused that first loss.

## Comparison with the v2 Apple Silicon Thunderbolt series

Sven Peter's v2 series introduces USB4 as a first-class Type-C mode, enforces PHY-before-ACIO startup, deactivates negotiated modes before safe-state transitions, and adds device links from the NHI to tunneled native ports. The Ubuntu 7.2 tree already contains the earlier Apple ACIO/NHI and ATCPHY implementation, but not the complete v2 Type-C representation or Apple NHI device-link hook.

The v2 TIPD change additionally quiesces DWC3 when the partner identity changes. It still does not cover a USB4-to-native-USB transition in which the partner and `USB_ROLE_HOST` stay unchanged. The local test patch detects that mode transition explicitly and performs a synchronous `USB_ROLE_NONE` transition before changing the mux.

The series cover also states that the published implementation supports XDomain and USB3-via-USB4, while PCIe and DisplayPort tunnelling are follow-up work. An NVMe enclosure requires PCIe tunnelling, so the current upstream series cannot by itself expose its SSD.

The current public `AsahiLinux/linux` `asahi` branch (commit `94fb23346d522edf53722357c426a3e58030beea`, compared file by file on 2026-10-28) is not a newer solution for this path: it has no `drivers/thunderbolt/apple.c`, and its ATCPHY driver still lacks the USB4 PIPE-handler selection that is present in the Ubuntu 7.2 test tree. For this investigation, Peter's v2 posting and the Ubuntu 7.2 integration are therefore the relevant code bases rather than the public Asahi branch.

Patch 04 of v2 extends the role quiesce condition with `partner_changed`; patch 16 adds the NHI-to-native-port device-link hook. Neither condition describes the observed fallback: the same partner remains present, the role stays `USB_ROLE_HOST`, and only the negotiated transport changes from USB4 to native USB. This is the specific gap exercised by `usb4-test2`.

## macOS trace comparison

The macOS Fanxiang trace records:

1. `USB3 mode change, powering off`,
2. `cable connected, powering on`,
3. immediate APCIEC register programming.

The Yottamaster trace repeatedly records a full PHY off/on cycle, including an approximately 52 ms off interval. This confirms that Apple does not leave the old USB3 path running while changing the link mode.

The Linux failure has the inverse ordering: the ACIO firmware reports the USB4 loss first; roughly 740 ms later `atcphy_mux_set()` warns because the PIPE handler is still active. The DWC3 Apple driver itself documents that DWC3 must exit host/device mode and the PIPE interface must return to the dummy backend before changing or shutting down the PHY. Calling the role switch synchronously is therefore using an existing required teardown path rather than introducing a new hardware sequence.

The APCIEC programming begins immediately after the mode transition under macOS. The Linux ACIO/NHI series establishes the USB4 control path but has no equivalent generic APCIEC-to-Linux-PCI host integration. The local prototype has already demonstrated that the external PCIe endpoint and NVMe driver work once APCIEC, DART, interrupts, and PCI ownership are configured.

## A/B results already available

| Test | Result | Interpretation |
| --- | --- | --- |
| NHI-to-native-port device links | Warning removed; approximately ten-second link loss remains | Fixes ordering/resume dependency, not the missing PCIe data path |
| CLx disabled | Link failure remains | Low-power link state is not the primary cause |
| Advertised speed capped | Link errors occur earlier and no stable device results | Does not support a Gen3-only signal-integrity explanation |
| Manual APCIEC/DART/IRQ/NVMe prototype | Stable 15-minute parallel read soak, reset, and repeated matching checksums | Physical endpoint and NVMe path are usable when Apple PCIe resources are configured |
| DWC3 quiesce on USB4 mode change (`usb4-test2`) | Same high-speed loss reproduced; synchronous teardown returned 0; `pipehandler=0`; no ATCPHY warning; ASM2464 reappeared as 10 Gb/s UAS | Fixes the USB4-to-native-USB fallback without masking the independent PCIe-tunnel failure |

## Current test patch

The `usb4-test2` kernel performs these changes only:

- detect USB4 mode changes independently of USB role changes;
- synchronously set DWC3 to `USB_ROLE_NONE` before ATCPHY is reprogrammed;
- log old/new link mode, role, mux target, and PIPE-handler state.

Expected success criteria are a clean fallback with `pipehandler=0`, no ATCPHY warning, and a usable native USB fallback. This patch is not expected to create the missing PCIe tunnel or keep a PCIe-only enclosure alive on USB4 by itself.

The 2026-10-28 boot test met all fallback criteria. The observed sequence was:

- 16.507 s: ACIO reports the same lane errors and `SBX disconnected`;
- 17.248 s: TIPD reports USB4 `1 -> 0` while the role remains host `1 -> 1`;
- 17.250 s: DWC3 quiesce completes with return value zero;
- 17.251 s: ATCPHY receives the native-USB target with `pipehandler=0`;
- 22.070 s: the ASM2464 enumerates as SuperSpeed Plus Gen 2x1;
- 23.124 s: the complete 4 TB disk is available through UAS.

The fallback disk then passed two matching 1 GiB SHA-256 reads (`f4d3753545e47372299f282014b1f76206af71757900be9228c002efdd9e9423`) followed by 294 seconds of continuous read traffic. It transferred approximately 273 GB at a steady 932 MB/s with no UAS reset, I/O error, USB disconnect, or ATCPHY warning. The block device was forced read-only for this test and restored afterwards.

The explicit full-PHY power-cycle variant derived from the macOS trace is retained as a diagnostic patch, but was not applied after the narrower teardown fix produced a clean 10 Gb/s fallback. Combining both changes would make it impossible to attribute the successful result and would add an unnecessary 52 ms outage to every transition.

## Required durable solution

The lasting NVMe solution is a generic Apple external-PCIe integration which is triggered by USB4 router discovery and removed on unplug. It must connect the standard Thunderbolt PCIe tunnel lifecycle to APCIEC power/reset, DART DMA mappings, interrupt routing, PCI bus enumeration, and teardown. Enclosure IDs can be used for diagnostics, but must not be the driver binding model.
