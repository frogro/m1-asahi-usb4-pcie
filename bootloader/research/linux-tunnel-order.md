# Linux reference order for the U-Boot external-storage path

This records the actual downstream Linux source audit requested after Probe17.
The reference commit and hashes of the working-tree files are in
`linux-tunnel-order-reference.json`. Existing project corrections are part of
that working tree; this is not a claim that every step exists in upstream Linux.
No proprietary driver source or disassembly is used.

## Host transport and router configuration

`apple.c:apple_cio_start` requires the negotiated Type-C mode and orientation,
PHY calibration, ACIO power/reset, M3 readiness, NHI-DART and NHI setup in that
order. The bounded RAM diagnostics through Probe16 cover these local stages.

`tb.c:tb_start` allocates the root switch, configures it and adds it before
normal topology discovery. `switch.c:tb_switch_alloc` reads the header and
finds capabilities. `tb_switch_configure` sets enabled, preserves the root
route/upstream port, sets the notification delay to 255 ms, selects the CM
version, and writes switch words 1–4. For the measured USB4 v1 header this
sets CM version 0x10. `usb4_switch_setup` is a no-op for route zero.

Probe17 read all seven host capabilities successfully, including Apple VSE at
0x35, but the first port-header read timed out with enabled=0. Probe19 added that configuration step with exact readback and then read all
seven host port headers successfully. This supports the missing root activation
as the cause of the earlier port-read timeout.

`eeprom.c` parses the exported host DROM and its lane pairing. The captured
M1 DROM has revision 1, 74 declared bytes in a 76-byte aligned property, valid
CRC8/CRC32C, and enabled ports 1–7. Ports 1/2 form lane 0/1 of one dual-link
pair. The published layout omits the device UID. Runtime validation is needed
before using this mapping; the boot code must not infer physical ports from
the response-port field alone.

## Link establishment and remote discovery

After domain setup, `apple.c` finds the Apple vendor capability, unlocks null
adapters, then writes negotiated cable information. `usb4_port_unlock` clears
only ADP_CS_4.LCK (bit31), preserving the other fields. Cable-info bits come
from CD321x: present, reverse orientation, active cable based on EUDO cable
type, and the Linux GEN3 flag. For the observed USB4 snapshot EUDO=0x2667e000,
the derived value is 0x11. It must be recomputed for each test/cable snapshot.

`tb_scan_port` scans only the primary lane, waits for a connected PHY state,
then addresses the downstream route. For this validated lane pair the first
external route is 1. The combined diagnostic stops after reading the remote
header: it does not configure the remote router or authorize storage DMA.
A valid host read or local cable-info readback alone is not proof of an
external link.

## External router and PCIe tunnel — subsequent work

1. Read remote capabilities, adapter headers and DROM, derive upstream/downstream
   roles, validate route depth, identify the PCIe adapters and available HopIDs.
2. Follow `tb_switch_configure` and `usb4_switch_setup` for the remote router:
   appropriate CM version, supported tunneling options and bounded RR readiness.
   Do not copy host assumptions to the remote ASMedia/Intel router.
3. Apply the required link configuration and call the equivalent of
   `usb4_switch_configuration_valid` before tunnels. It waits for CR; on a host
   router this operation is deliberately a no-op.
4. Reproduce `tb_tunnel_alloc_pci`/`tb_pci_pre_activate`: select the matched
   host PCIe-down and device PCIe-up adapters, verify LTSSM Detect where required,
   allocate both paths and calculate flow-control credits from actual adapters.
   `path.c` programs HopIDs and enables each path; merely enabling an adapter
   is not a complete tunnel. `tb_pci_activate` enables destination then source.
5. Preserve the project-specific native-host notification ordering from
   `tb_native_pci_tunnel_changed` and the PCIe-C driver. Nested tunnels must not
   reset the root controller. U-Boot will need an explicit equivalent to these
   Linux callbacks, not Linux runtime-PM/workqueue code copied unchanged.
6. Enumerate PCIe and NVMe, verify identity/capacity and perform a bounded
   read-only hash test. Only then evaluate filesystem/GRUB loading.

## Separate PCIe-C prerequisite and DMA lifetime

`apple_cio_start` creates the tunneled PCIe children after NHI/router readiness.
Before creating their DART, `apple_pcie_tunnel_prepare` makes the PCIe-C clocks
and non-posted fabric live, applies debug/fabric/port/OE/RC tunables in order,
initializes RID-to-SID entries and waits for READY. Accessing that DART too
early was a source of asynchronous SError in the existing Linux work.

This is a different DART from the NHI SID1 IOMMU. The tunneled PCIe DART at
0x521008000 has a different layout and 64 streams; do not reuse NHI register
assumptions. PCIe-C early clocks/reset, DART translation and external NVMe DMA
need separate checked ownership. Exit to GRUB/Linux requires a designed
handover or complete quiesce/cleanup. All current RAM probes retain their DMA
allocations and require full reset; they are not yet an external boot driver.

The tested kernel reference enables USB4/Apple support, Apple RTKit/Type-C,
Apple PCIe-C/hotplug and DART. Kconfig availability alone is not evidence of
bootloader initialization or hardware support. The excluded Linux reset-ACK
classification change is not part of this work.

## Expanded Type-C-to-NVMe audit (31 October, Linux reference comparison)

The sequence below is a dependency order, not a claim that Linux executes
every callback on one thread. Probe, connection-manager events, authorization
and PCI enumeration can overlap. In particular, a boot-time PCIe host probe
can precede authorization. The saved `7.2.12-usb4sd4-egpu2` binary and the
subsequently modified source tree must be distinguished: later source fixes
are not evidence that they are present in this binary.
The expanded source hashes and live-artifact hashes are recorded in
`linux-full-chain-reference.json`; raw live device-tree, configuration and
journal captures remain in the local research archive.

| Stage | Linux source / operation | Bootloader consequence |
| --- | --- | --- |
| PD-controller readiness | `tipd/core.c`: `switch_power_state(...S0)` reads SYSTEM_POWER_STATE (0x20), conditionally sends `SSPS`, reads back; APP firmware check follows | Our status-only snapshot does not yet inspect this register. First measure it; do not assume `SSPS` is necessary. |
| Connection snapshot | `cd321x_update_work`: plug, power/data role, orientation, identity, negotiated USB4 EUDO or TBT mode | Use current negotiated values. Linux derives orientation from STATUS bit 4; the diagnostic currently reports DATA_STATUS bit 1. Both indicated normal orientation in the observed case, so a mismatch is not established as its cause. |
| Existing USB consumer | Quiesce DWC3 to USB_ROLE_NONE before PHY changes when connection/mode changes | Preserve the tested halted-controller/reset discipline; do not change active USB lanes underneath a consumer. |
| PHY bootstrap | `atcphy_probe_finalize`: assert DWC3 reset, power down inherited PHY state, initialize PIPE handler | Firmware handoff state is not a replacement for explicit bootstrap. |
| PHY connection | Orientation, mux USB4/TBT mode, wake small/big domains, unclamp/APB reset, mode tunables, clocks, lanes, PHY reset release | Source calibration and address ranges from the actual device tree and hardware variant. |
| ACIO activation | `apple_cio_start`: PCIe-C reset before ACIO power, domain links, ACIO reset deassertion, M3 start, RTKit boot, ready poll, RC tunables | Each ready condition is separate; a live mailbox alone is insufficient. |
| NHI dependency | Populate ACIO children; `apple_nhi_probe` defers without IOMMU attachment | NHI DMA must not begin before its DART stream and mappings are usable. |
| NHI transport | 42-bit DMA mask, NHI tunables, PDF/IRQ setup, ring count validation, connection-manager domain/control transport | Boot polling replaces Linux IRQ/workqueue mechanics but must preserve DMA ownership and completion semantics. |
| Host router | Root allocation/configuration, capabilities and DROM, enable/CM version/notification delay, domain registration | Already reached by RAM probes; preserve route-zero-specific behavior. |
| Physical connection trigger | Unlock null ports, then write Apple cable information derived from negotiated Type-C state | Write order matters. Local readback is not proof of link training. |
| Events and link | Acknowledge control events; scan primary lane; wait for connected port | Probe21 fixed repeated event acknowledgements; Probe22 still observed state 7 on both lanes for five seconds. |
| Remote router | `tb_scan_port`: allocate/configure/add remote switch; configure link; downstream retimers; CLx/TMU; configuration-valid; upstream retimers | Derive topology and resources; do not substitute an OWC-specific fixed adapter table. |
| Authorization | PCIe tunnel creation may be deferred until user-space authorization | A bootloader needs an explicit selected-device policy and must build the tunnel before expecting the PCIe endpoint. |
| PCIe transport | Select PCIe-up/down adapters, allocate both paths/credits/HopIDs, LTSSM Detect prerequisites, activate paths and destination/source adapters | Host or remote router discovery does not yet expose a usable NVMe device. |
| PCIe-C/DART prerequisite | Cold fabric/clock setup, ordered tunables, RID-to-SID initialization, READY, then instantiate the separate PCIe DART | Do not confuse the NHI DART with the 64-stream tunneled PCIe DART. |
| Native host notification | `tb_native_pci_tunnel_changed` after tunnel activation; release/reset/link and topology handling | The saved binary can miss activation after an early host-probe failure. A later prepared retry fix is a separate change. |
| PCI enumeration | Host bridge/MSI/ECAM setup, bus enumeration, address windows/BAR allocation, RID-to-SID mappings and device enable | These are required before endpoint DMA; a working configuration read alone is insufficient. |
| NVMe | `nvme_probe`: PCI enable, controller/admin setup, identify/init completion, I/O queues, namespace discovery | Identify capacity, then bounded read-only verification; no filesystem writes for bring-up. |
| Boot handover | Quiesce transport and endpoint DMA, maintain/remove mappings according to a defined handover, load boot files | Current RAM probes require full reset and do not yet implement this handover. |

On the second saved-Linux boot, without a cable change, the journal again
showed both lanes enter CL0 and recognized the OWC Express 1M2, followed by
native-host reset-release timeout and later link errors. This proves Linux
passes the earlier physical-link stage that U-Boot currently misses; it does
not establish a stable complete Linux NVMe reference in this particular boot.
The conditional S0 transition, initial PHY state, and RTKit endpoint handling
remain comparisons to measure, not established fixes. In particular U-Boot's
current diagnostic does not start the SYSLOG endpoint, so absence of Linux-like
firmware log lines is not itself evidence of stalled firmware.

The current Probe22 U-Boot configuration already enables `CONFIG_NVME_PCI=y`.
The original baseline did not, so inspecting the baseline alone gives the
wrong answer. This is not presently a missing generic NVMe configuration flag.
The live Linux `/soc` contains 36 tunable/DROM properties. The input DTB given
to the m1n1 probe contains none of these before runtime export; that difference
must not be reported as missing runtime calibration, because earlier probes
explicitly verified the runtime-exported tunables. A byte comparison requires
capturing the final runtime DTB, not comparing only these two input files.

### Successful live reference after physical OWC reconnect

The user subsequently confirmed physically reconnecting the OWC. In the same
saved egpu2 boot, USB4 transition occurred at monotonic 365.216 s, both lanes
reached CL0 at 365.689 s, the remote router was identified at 365.702 s,
tunnel paths became active at 366.352 s and PCIe link-up followed at 366.353 s.
NVMe I/O queues were ready at 366.510 s. The native host bound without the
helper issuing its manual `drivers_probe` operation. The helper's earlier
authorization write returned EINVAL; later sysfs reported authorized=1.
Do not describe that failed helper command as the successful recovery.

The live link reported two lanes at 20 Gbit/s per lane in each direction.
The Crucial CT4000P310SSD8 appeared through ASMedia PCIe bridges. A direct
64 MiB read completed successfully; its newly recorded SHA-256 is
`aa2d018770bac11609b35427f57593fc8c80ba1ab315cf2563f9cae8b9a150da`.
This was not a comparison against a previously known checksum. No external
filesystem was mounted and no SSD writes were issued by the test.

Captured locally: 24 router/adapter/path/DROM debug files, the Thunderbolt
packet-event trace, complete monotonic kernel journal, live DTB and kernel
configuration. These give an actual working reference for later tunnel
implementation; U-Boot still has not reached the external router. The raw
captures are retained locally because they include hardware identifiers.
