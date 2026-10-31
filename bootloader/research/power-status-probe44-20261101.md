# Probe44: bounded CD321x power-status observation

Probe43 matched all 61 reviewed powered PHY/PIPE/USB2 registers against the
connected custom Linux reference, but remained in Phase2. The user observed
that the OWC LED may have been off; its timing was not confirmed. This is an
observation to investigate, not proof of missing VBUS.

Existing register 0x20 is SYSTEM_POWER_STATE. Probe44 adds read-only
POWER_STATUS (0x3f, documented two-byte prefix), STATUS (0x1a) and the system
power state at twelve points at most: before USB-host removal and PHY start, ten link observations,
and after ACIO shutdown. There are no power commands, interrupt clears, role
changes or additional PCIe-C initialization writes. All sampling is optional
and selected only by `atcm1 1 usb4power`; Probe43 remains available unchanged.
Sampling adds I2C latency, so it cannot be described as timing-identical.

The helper validates vendor 0x28 and APP mode, rejects unexpected register
lengths, and leaves its result unchanged on error. STATUS is read twice to
reject a change observed across the sample. This does not make sampling
atomic or rule out brief power drops. A failed polling observation disables
further polling observations for that attempt; the separate post-shutdown
sample can still be taken. Existing bounded link timeouts and reset remain.

On this CD321x, register 0x3f reports a ten-byte length. Linux tipd consumes
its two-byte prefix and permits longer lengths. The diagnostic accepts only
the two-byte documented size or this measured ten-byte extension; it does not
relax all length validation. The first read returned bytes `0a 0d 00`.
The regression tests exercise both accepted lengths, other lengths at all six
read positions, transport errors, vendor/mode mismatch and observed change.

The preliminary stock-Linux sample has STATUS 0x108280ef, POWER_STATUS 0x000d,
SYSTEM_POWER_STATE 0 and native USB data status 0x71. Its power fields indicate
connection=1, source_sink=0, opmode=3 according to Linux's definitions. This is
explicitly a native-USB power reference, not the connected USB4 PHY reference
from Probe43. Raw status interpretations specific to generic TI devices must
not be used as a physical voltage measurement for Apple's CD321x.

Register definitions and protocol handling come from the open-source Linux
`drivers/usb/typec/tipd/core.c` and `tps6598x.h`. Original TI/Asahi attribution is
retained in the library. No Apple disassembly or new firmware extraction is
involved. The next hardware result must distinguish reported controller
state from actual OWC supply voltage. No new power fault or fix is claimed.
