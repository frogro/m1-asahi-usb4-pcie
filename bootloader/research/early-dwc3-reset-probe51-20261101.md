# Probe51: isolate the early DWC3 soft-reset pulses

Prepared RAM-only comparison against Probe48; not hardware tested yet.
Startup analysis found that ordinary `usb start` pulses the DWC3 core and
USB2/USB3 PHY soft resets before our explicit ATC/ACIO sequence. Equal PMGR
states in Probe50 do not rule out consequences of these pulses.

A per-device property with the exact tag 51 enables the alternative only for
J274 /soc/usb@502280000, with the expected compatible and resource address/size.
An absent property leaves the ordinary path unchanged. A malformed property,
wrong board/port/resource, unknown core ID, all-ones reads or already asserted
reset bits reject the diagnostic. The existing preserve-PHY common setup is
then used; both original 100-ms waits are retained. Subsequent xHCI reset and
the complete explicit ATC/ACIO/NHI/PCIe-C diagnostic remain unchanged.

The frozen build configuration is byte-identical to Probe48, including its
normal USB preboot and console choices. The input DT differs only by the
per-device flag and test label; bootcmd differs only by the label. Probe50's
new PMGR command remains compiled but is not invoked. This is a sequential
comparison with the earlier run, not a claim that all external starting
conditions or software execution timing are identical.

26 host cases exercise the actual selection/preflight bodies with libfdt,
ASan and UBSan: default path, board/port/resource/tag rejection, inherited
reset rejection, both retained delays, and error propagation. The common
DWC3 initialization is stubbed in these host cases; they do not prove physical
link behavior. The final M1 build and seven payload hashes are verified.

The runner must confirm the early preserve marker, actual controller activity,
PHY/PCIe-C readiness, firmware phases/lane states, internal control hashes,
planned reset, and stock Ubuntu return. `usb start` shell success alone is
insufficient. There is no new external sector command; normal USB enumeration
and existing NHI control DMA still occur. No installed boot file is changed.

The startup-audit proposal of a completely unprobed-controller entry remains
separate. This narrower comparison avoids rewriting that lifecycle at the
same time as changing reset behavior. No permanent driver fix is claimed.
