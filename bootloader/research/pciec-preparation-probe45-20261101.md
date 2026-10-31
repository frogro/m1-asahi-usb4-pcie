# Probe45: native PCIe-C preparation before USB4 link training

Probe43 matched 61 powered PHY/PIPE/USB2 register values against working Linux.
Probe44 additionally observed unchanged CD321x power reporting in twelve
samples; the OWC LED was not visible to the user. Neither probe reached Phase3.
Reported power state is not a voltage measurement and does not exclude a brief
unobserved drop. No speculative VBUS command is added.

The working Linux trace completes native PCIe-C cold preparation before
Phase2/Phase3. The RAM-only U-Boot path previously powered/reset that block but
did not apply `apple_pcie_tunnel_prepare()`. This is a concrete difference,
not evidence that it causes the Phase2 stall. Probe45 tests this one difference.

The `usb4pciec` selector keeps Probe44's bounded NHI queries, PHY/power
observations and xHCI lifecycle. A one-shot callback runs after successful
host inventory/queries and before lane unlock and cable submission. It checks
all five shared ACIO/PCIe power domains, prepares only native PCIe-C port1,
and returns before any native PCIe DART, PCI enumeration or DMA is enabled.
A preparation error prevents the subsequent lane/cable stage. Powered state
is retained until the existing mandatory reset; no partial rollback or retry.

The callback follows the project's tested Linux sequence: debug/fabric
tunables, 21 cold-reset writes, clearing 64 requester-to-stream mappings, port
tunable, PERST release, APPCLK enable/ungating, OE-fabric/config tunables,
counter enable and status clears. It polls READY at 10us with a 250ms bound.
An already-ready port skips the initialization, as Linux does; all-ones status
is rejected. The UART records reads/writes so a skip cannot be mistaken for
fresh initialization. It never enables LTSSM or assigns an endpoint stream.

The diagnostic device tree receives five properties containing 43 tunable
triples from the saved working Linux DT. Before any hardware access, the
code checks J274 compatibility, disabled native-controller/port nodes, exact
addresses/resource sizes and all 43 exact offset/mask/value triples. This
experiment is deliberately limited to the measured J274 port1 configuration,
not yet a generic implementation for all Apple SoCs. All original register
resources remain unchanged and the nodes remain disabled for automatic probing.

All four native PCIe-C unit tests and the existing regression set must pass
(73 sandbox tests total). Mocked reads/writes are independently compared with
the Linux source sequence and saved DT: 178 operations on the zeroed model,
including fault injection at every position, 129 corrupted tuple fields and
ten invalid counts. Ready, delayed-ready, all-ones and timeout paths are
covered. The same production library/tests run under ASan and UBSan. These
are software checks, not claims of successful hardware PCIe-C initialization.

The source retains the original Linux PCIe driver attribution. Configuration
values come from the already saved DT; there is no new Apple disassembly or
firmware extraction. The preparation modifies only a RAM-loaded diagnostic
payload. Installed boot files, external SSD contents and the kernel installer
are unchanged. The existing 60-second watchdog is configured, but cannot be
claimed as a guaranteed recovery from arbitrary hardware failure.

The complete development source is preserved in [the cumulative patch](probe45-cumulative-source.patch), with a [hash manifest](../validation/probe45-cumulative-source-manifest.json). It reconstructs all 50 modified/new source files byte-for-byte over the pinned base.
