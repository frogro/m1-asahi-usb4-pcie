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
