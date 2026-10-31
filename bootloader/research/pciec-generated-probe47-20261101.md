# Probe47: supply PCIe-C tunables once

Probe46 identified the first rejected property: `apple,tunable-debug` arrived
in U-Boot with 24 bytes, although the frozen input DT contains 12 bytes and the
Linux reference contains one 12-byte triple. The unchanged boot stage therefore
changed this property before U-Boot. Appending a second generated triple is
the working hypothesis; the run did not dump those 24 bytes, so their exact
contents have not yet been established.

Probe47 removes only the five pre-populated PCIe-C tunable properties from the
input DT. Both complete PCIe-C nodes now match the original Probe44 input.
The U-Boot executable, boot-stage executable and all validation checks are
byte-identical to Probe46. Generated values must still match the 43 Linux
reference triples exactly before any PCIe-C initialization is attempted.
Missing or differing values still abort; nothing is substituted silently.

This tests both the property-generation hypothesis and, if validation passes,
the originally intended bounded PCIe-C preparation. There is no external disk
I/O or PCIe tunnel. The installed boot files are not modified.

## Hardware result

The generated debug, fabric and port0 properties have the expected lengths
and all 29 triples match the Linux reference. The next property, oe-fabric,
is absent; validation stops there, so config/rc availability is still unknown.
This establishes that the boot stage supplies only part of the required
preparation data. Native PCIe-C initialization has still not run.

Both internal NVMe control hashes matched; the planned reset and automatic
stock-Ubuntu return were verified. The boot bundle is unchanged and GRUB's
next_entry is empty. No external disk was accessed.
