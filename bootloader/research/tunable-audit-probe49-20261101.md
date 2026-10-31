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
