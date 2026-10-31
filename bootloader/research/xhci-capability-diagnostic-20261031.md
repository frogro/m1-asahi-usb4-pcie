# Probe35 outcome and Probe36 capability diagnosis

Probe35 completed DWC3 core initialization and both checks of inherited USB
DART bypass. The xHCI capability guard returned -EPROTO before allocation,
reset or RUN; its inputs were not logged. Therefore this is not evidence
against starting xHCI as a prerequisite for link progression. 41/41 NHI
control responses were received; Phase2 was observed, no Phase3 or remote
router. Internal NVMe hashes matched and the automatic reset returned stock
Ubuntu with unchanged installed boot bundle and empty GRUB next_entry.

A guarded Linux read was also attempted, but its runtime-active prerequisite
failed; no register comparison was obtained and the guard was not bypassed.

Probe36 only captures each of the existing six capability inputs once and
prints them before the identical acceptance predicate. No bounds are relaxed.
All Probe35 scope limits remain: retained diagnostic context, verified USB
DART bypass, no USB enumeration/storage requests, no external PCIe tunnel or
SSD access, mandatory reset and watchdog. No installed changes.

Validation: M1 build, 33 extracted start/stop/capability/DMA/port cases with
ASan/UBSan, four source contracts, unchanged configuration, exact one-file
patch reconstruction. The prior 63 sandbox tests were not repeated for this
logging-only change. Hardware outcome pending.
