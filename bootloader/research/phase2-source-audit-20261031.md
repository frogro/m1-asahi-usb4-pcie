# Phase2 link-start audit, 31 October 2026

## Finding and next experiment

The prototype switches the DWC3 PIPE handler from its dummy clock/mux to
USB4 **before** starting ACIO. The inspected Linux call chain configures the
core ATCPHY first, starts ACIO/NHI and submits cable information, and only then
requests the USB host role whose PHY callback configures PIPE. Matching final
register values did not establish this ordering. This is a concrete difference,
not yet proof that it causes the Phase2 stall.

Probe29 tests only this interleaving against Probe28. It splits the existing PHY
routine, preserves its writes, delays and halted-DWC3 check, and leaves PIPE on
the dummy clock until cable-info write/readback succeeds. The one-use callback
then performs the unchanged PIPE handshake before bounded lane polling. The
DWC3 reset release remains before ACIO, as in Probe28; the controller remains
halted. No host USB enumeration, PCIe tunnel or external SSD writes are added.
The proposed calibration no-op-write change is saved separately and is **not**
part of this comparison.

## Pinned source scope

- U-Boot base: `b33034a515a068381c4aa28831fb709e91300cd1` plus archived research patches.
- Local Linux source: `517fe27a2ce7fa8d03aa6705a10ff4422197ff5d`.
- Current Asahi `asahi` branch inspected via GitHub:
  `a7c69b66c79296a8b51e1555ac887fa6de2d07be`.
- Working saved Linux binary: `7.2.12-usb4sd4-egpu2`. The local checkout is
  newer; this is not a claim that its source exactly reproduces that binary.

Twenty-five extracted PHY helpers, including the USB3 set-mode and DWC3 reset
callbacks, are byte-identical between the local reference and current Asahi.
The whole files differ because the local tree includes later project work.
There is no newly missing PHY helper among these 25 functions.

Relevant local call chain:

1. `drivers/usb/typec/tipd/core.c:cd321x_update_work` stops the old USB role
   where required and calls `cd321x_typec_update_mode`.
2. The USB4 branch calls `typec_mux_set`, reaching `atcphy_mux_set` and
   `atcphy_configure`. This initializes core PHY power, calibration, clocks,
   lanes and PHY reset; it does not select USB4 PIPE.
3. `typec_thunderbolt_switch_set` reaches `apple_cio_start`: power/reset,
   M3/RTKit boot, firmware-ready check, RC tunables, then NHI/DART children.
4. `apple_nhi_probe` applies NHI tunables, starts the connection manager,
   unlocks the host lane ports, writes cable information, and completes the
   parent wait. The parent's additional PCIe setup precedes its return.
5. Only after this returns does `cd321x_update_work` request the USB host role.
   `dwc3_usb_role_switch_set` schedules DWC3 mode work. Host initialization
   reaches `phy_set_mode` / `usb_phy_roothub_set_mode`, and
   `atcphy_usb3_set_mode` calls `atcphy_configure_pipehandler`.

This establishes source call ordering. It does not establish exact scheduling
latency in the saved Linux binary, nor prove that DWC3 remaining halted is
irrelevant. That is an explicit remaining difference from full Linux.

## Cross-check matrix

| Area | Evidence | Remaining limit |
|---|---|---|
| PHY/RC/NHI calibration | Earlier runtime-DT comparison matched 12 arrays, 543 triplets | Linux skips unchanged calibration writes; prototype previously always wrote. Separate candidate saved, not hardware tested |
| PHY write sequences | Extracted actual Linux helpers and U-Boot routine executed against fake MMIO: USB4/TBT, both orientations, three initial patterns (12 cases) | With the separate no-op calibration candidate, only extra 10-us DWC3-release delay and redundant lock-clear remained; does not simulate analog hardware or ACIO interleaving |
| Current upstream PHY | 25 helper functions match current Asahi exactly | Not every Linux driver or the entire binary |
| Final PHY/PIPE state | 17 allowlisted live registers equal in working Linux and Probe26 | Final state cannot prove order or transient state |
| ACIO power/reset/M3 | Source order and previous hardware readiness agree; firmware build string agrees | Not a full bus-write capture of all Linux power-domain internals |
| DART and control DMA | Hardware map/readback, host control replies, bounded fault checks passed | Control DMA is not a PCIe SSD tunnel |
| Host configuration | Root enable, CM version, notification delay match saved Linux writes | Linux does additional router queries, documented below |
| Cable metadata | DROM pair validation, orientation, EUDO and host cable word `0x11` match | Same metadata alone does not prove PHY/link startup |
| TMU and events | LOWRES TMU setup and root-event ACK implemented and tested | Neither alone advanced Phase2 |
| Timing/logging | Probe28 reduced rings-to-cable interval 276 to 146 ms | Still Phase2 after 5.081 s; logging overhead alone not demonstrated cause |
| PIPE ordering | Different interleaving found in source chain | Probe29 late PIPE succeeds, link still Phase2 |

The fake-MMIO comparison uses real source functions and records writes/delays;
power/lock reads are modeled as successful. It is not a hardware test and
cannot validate Linux scheduling, initial hidden state or analog training.

## Complete pre-cable control-write review

The saved working Linux trace was reviewed up to its cable-info write at
365.223820 seconds, rather than comparing only selected end-state registers.
Besides the reproduced root configuration, TMU, port unlock and cable metadata,
Linux issues router operation requests:

- opcode `0x25`: NVM sector-size query (not firmware programming);
- opcode `0x33`: read preferred buffer-allocation parameters;
- opcode `0x10`: query DP resource availability for adapters 5 and 6.

These use metadata register `0x19` and command register `0x1a`. They are not
blindly replayed: source identifies them as queries, while their possible
firmware side effects have not been experimentally excluded. No NVM write or
authentication operation is proposed.

Linux also clears `ADP_CS_5_DHP` on lane port 1. Its trace reads and rewrites
`0x0000b016`; the bit was already clear. Probe28's port header contains the
same value, so there is no demonstrated missing hotplug-enable bit in this run.
`usb4_switch_setup()` returns immediately for the host/root router; its
PCIe/USB3 tunneling enable writes apply to a remote router after discovery and
cannot simply be moved ahead of discovery as a supposed Phase2 fix.

## Mailing lists and current PRs

The firmware's logged **Phase2** is distinct from **m1n1 stage 2** in Asahi boot
documentation. Searches for both meanings must not be mixed.

Primary sources checked:

- [Sven Peter, initial USB4/TB v2 cover, 6 September](https://lore-kernel.gnuweeb.org/linux-usb/20260906-b4-apple-soc-tbt-v2-0-1f80085f93fb@kernel.org/): strict PHY-before-ACIO prerequisite, M3-owned NHI/DART lifetime and out-of-band cable data.
- [Apple Silicon driver patch v2 19/22](https://lists.openwall.net/linux-kernel/2026/09/06/842): ring layout, buffer assignment, readiness and cable submission.
- [Sven's review response, 8 September](https://lore-kernel.gnuweeb.org/linux-usb/22808191-5310-4d90-9fac-68d0d85b4c54@kernel.org/), [Mika's response, 9 September](https://lore-kernel.gnuweeb.org/linux-usb/20260909060615.GJ106095@black.igk.intel.com/): ring settings latch with valid/enable, and proposed movement of cable-info handling into the connection manager. This is an architectural review, not a verified Phase2 repair.
- [USB4 PIPE handler patch, 21 August](https://lists.openwall.net/linux-kernel/2026/08/21/1270): separate USB3-to-NHI PIPE routing sequence; already present in the inspected PHY source.
- [U-Boot Apple documentation](https://docs.u-boot-project.org/en/latest/board/apple/m1.html): m1n1 payload, runtime device tree, existing NVMe and USB Type-C support. It does not document an Apple USB4 boot connection manager.
- Asahi PRs [515](https://github.com/AsahiLinux/linux/pull/515), [574](https://github.com/AsahiLinux/linux/pull/574), [607](https://github.com/AsahiLinux/linux/pull/607) and current source: dummy PIPE fallback and M3-specific PHY/display work do not provide a demonstrated fix for this M1 Phase2 stall.

No directly applicable, published Phase2 boot fix was located in these searches.
This is a bounded search result, not proof that no relevant message exists.
Direct lore access was unreliable; primary-message mirrors were used. No Apple
disassembly or proprietary driver source was used for this comparison.

## Acceptance boundary

A passing PIPE step alone is insufficient. The required next observation is
Phase3/Connected and a valid remote-router configuration reply. Storage boot
still additionally needs PCIe tunnel resource setup, PCIe-C/DART enumeration,
read-only SSD hash verification, EFI block access for GRUB and safe OS handover.

## Probe29 result

The delayed PIPE callback returned zero and reached its final state after cable
readback. Both lanes nevertheless remained in state 7 throughout the bounded
observation and firmware still stopped at Phase2. All 61 control requests were
answered. Internal NVMe hashes before and after match and reset was observed.
Thus changing PIPE interleaving alone is insufficient; this is not a link fix.
Stock Ubuntu return was confirmed by SSH; `next_entry` is empty.

## Probe30 preparation

Probe30 adds the separate no-op calibration change on the measured Probe29
baseline. The source delta reconstructs all three files exactly; the M1 build,
60 sandbox tests, 45 RC/NHI calibration fault cases and the twelve extracted
PHY sequence comparisons passed. Explicit power/reset writes are unchanged.
This tests one additional variable; hardware outcome follows below.

## Probe30 result and remaining comparison

The candidate skipped 13 of 29 RC and 81 of 226 NHI calibration writes.
Late PIPE succeeded, all 61 control requests received replies, but firmware
still stopped at Phase2 and no remote router was read. Internal NVMe hashes
matched, reset completed and stock Ubuntu returned over SSH. The installed
boot bundle checksum is unchanged. Neither Probe29 nor Probe30 is a link fix.

Next compare DWC3 core state, not just the ATC/PIPE snapshots: the diagnostic
keeps xHCI halted while Linux proceeds into host operation. Linux core.c
explicitly clears GUSB3PIPECTL.SUSPHY before PHY initialization and changes
PHY suspend state during mode transitions. Read the actual working Linux
registers and corresponding bootloader states before proposing new writes.
This remains a hypothesis, not evidence that starting xHCI fixes Phase2.
RTKit power-message ordering is another remaining comparison; the extracted
PHY mock tests do not cover it. No new hardware run is scheduled here.
