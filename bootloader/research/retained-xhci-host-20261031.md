# Probe35: retained xHCI host-start comparison

Base is Probe34, whose Yottamaster TB3 link stayed at Phase2 despite 61/61
host-control responses. Probe32 USB4 reached the same stopping point.

Linux reference is the recorded 517fe27a2ce7fa8d03aa6705a10ff4422197ff5d checkout:
`drivers/usb/dwc3/dwc3-apple.c` documents PHY, DWC3 core init, PIPE switch,
then host start. The diagnostic previously omitted normal DWC3 core init
and stopped xHCI throughout observation. This experiment adds U-Boot's
existing core-init and lowlevel host-start paths; it is not a claim of full
Linux DWC3 feature/configuration equivalence.

Only explicit `atcm1 1 hostrun` invokes the additions. `host` keeps the
previous staged PHY/CIO path. All ordinary xHCI contexts have the new
M1 diagnostic flags clear and retain their prior startup behavior.

Before core initialization and host start, both USB DART references must
match the selected J274 port: 0x502f00000/SID0 and 0x502f80000/SID1. Both
must already be active, be powered, report bypass support and exact existing
TCR=0x1100, and have no valid error bit. No DART modes or tables are changed.
This inherited USB bypass differs from the independent translated NHI DART.
Unknown/translated USB DART state aborts this experiment before RUN.

The removed USB device's freed private context is not reused. A separately
allocated xHCI context invokes the normal reset, ring/scratchpad allocator
and RUN sequence. Every diagnostic DMA mapping must match its allocated
physical address and fit the checked size. Failed mapping or scratchpad
allocation blocks RUN. Capabilities bound port count, scratchpad count,
register offsets and page-size presence. Root port power uses the normal
neutral RWS mask, with no port reset or W1C event clearing. No USB children
are enumerated and no transfer doorbell or storage command is submitted.

The context and all DMA allocations remain retained on success or failure
until full reset. After the NHI observation returns, the diagnostic clears
RUN and checks HALTED without freeing or resetting the PHY. Mandatory full
reset and the guest watchdog remain in place; a host-side timeout cannot
recover an arbitrarily hung target on its own. No installed boot changes.

Verification: 63 sandbox tests; 99 cases using extracted production functions
with ASan/UBSan and mocked hardware/allocation (33 start/stop/capabilities/DMA/
port, 26 dual-DART preflight, 30 DWC3 setup, 10 actual lowlevel-init RUN guards).
Four source-order/retention checks complement those executions. These do not
prove hardware timing, allocation success or firmware link progression.
The M1 build and exact four-file patch reconstruction are prerequisites.
Hardware outcome pending; success criterion is link progress and a valid
external-router header, not external NVMe boot.
