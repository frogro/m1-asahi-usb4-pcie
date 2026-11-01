# Probe49: complete tunable handoff comparison

Probe48 proved native PCIe-C readiness but did not advance USB4 beyond Phase2.
This audit compares the seven tunable properties consumed by the PHY, ACIO
and NHI diagnostics with the saved working Linux DT (509 triples). It examines
the actual U-Boot control FDT, after the unchanged boot stage has processed it.
Each property is hashed with SHA-256; missing or different lists are reported,
and a differing list is printed for exact comparison.

The U-Boot executable and boot-stage executable are unchanged from Probe48.
Only bootcmd changes. This run does not invoke ATC, ACIO, PCIe-C or NHI
initialization. Normal U-Boot startup still initializes USB/internal NVMe as
before; no external storage read/write command is issued. The same internal
control file is read and hashed before/after, followed by the mandatory reset.

Four actual sandbox command runs verify all-seven-match, a missing property,
a modified tuple and a duplicated list. The expected classifications and
number of matched groups were asserted. These command tests do not simulate
boot-stage property generation; that is the hardware observation being sought.

## Hardware result

All seven actual handoff properties match the saved working Linux DT exactly
in byte length and SHA-256 (509 triples total). No list was missing, duplicated
or different. The mismatch-print branch was therefore not needed.

This run did not initialize PHY/ACIO/NHI or attempt a link. The runner's
legacy PHY/NHI/ACIO boolean fields are false because those steps were not run,
not because new hardware failures occurred. Internal control hashes matched.
The planned reset, stock-Ubuntu SSH return, unchanged boot bundle and empty
GRUB next_entry were verified.

The input-list mismatch hypothesis is not supported. This does not prove
identical transient hardware state or timing: matching lists and selected
register snapshots cannot replace a complete sequence comparison. No
unchanged hardware repeat is requested.

## Bounded follow-up source review

Linux's cold probe also resets DWC3, powers down inherited PHY state and
selects the dummy PIPE mux, as the prototype already does. The inspected
M1 post-tunable/lane sequence and USB4 PIPE lock/mux/unlock operations are
represented. RTKit readiness is not missing an AP-ON request: Linux performs
it at the end of boot, while this prototype calls and waits for it explicitly
after its IOP-ON wait and before firmware readiness/tunables.

This is a limited source review, not a proof of timing or whole-system
equivalence. Asynchronous firmware servicing, transient states and inherited
cable/peer state remain comparison targets. No new specific missing operation
was established by this review; no hardware modification or further probe
is armed on that basis. See the source-hash manifest for the exact files read.
