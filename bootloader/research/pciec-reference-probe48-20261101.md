# Probe48: separate generated and saved reference tunables

Probe47 established that the unchanged boot stage supplies correct debug,
fabric and port0 lists but does not supply oe-fabric. Config/rc was not reached.
The five saved Linux reference lists now reside under distinct
`/config/u-boot,probe-pciec-*` properties, leaving generated `apple,*` lists
unpopulated in the input DT. A generated list always takes priority. Only
an absent list selects its explicitly logged saved reference. A present
but wrong-length or different generated list still aborts even if a correct
reference is available. The selected 43 triples must match the same exact
compiled Linux reference before hardware preparation begins.

The preparation sequence, addresses, timeouts and all other source files are
unchanged. This remains a machine-specific diagnostic, not a generic boot
implementation. No native PCIe DMA, tunnel or external disk access is enabled.

The M1 build and patch reconstruction passed. 32 ASan/UBSan host tests execute
the actual preflight body with libfdt and thin U-Boot API substitutes. They
cover generated-only, reference-only and mixed lists, missing lists, malformed
and duplicated generated lists despite valid fallback, malformed fallback,
and enabled/wrong hardware nodes. Rejections occur before resource mapping.
These tests do not emulate actual boot-stage generation or establish hardware
success. The unchanged cold-initialization logic retains prior Probe45 evidence.

## Hardware result

All 43 triples passed validation. The boot stage supplied debug, fabric, port0
and config/rc; only oe-fabric used the saved reference. Native PCIe-C cold
preparation performed 48 reads and 114 writes and returned success with
PORT_STATUS=0x3. It completed before lane unlock and cable submission.

This was insufficient to establish a USB4 link: both lanes remained in state 7
(TB_PORT_UNPLUGGED in the Linux reference), firmware reported Phase2 without
Phase3, and no remote router was read. NHI answered 81/81 control requests;
the result was -110. All 61 sampled PHY/PIPE/USB2 registers still matched
working Linux. Twelve CD321x power-state samples remained identical.

Both internal control hashes matched. The planned reset and automatic return
to stock Ubuntu were verified over SSH, with the original boot bundle hash
and empty GRUB next_entry. No external SSD was accessed.

The next comparison is the complete set of seven PHY/ACIO/NHI tunable arrays
at handoff. The register snapshot samples only selected locations. Probe49
will hash all 509 reference triples and print differing lists, without new
PHY/ACIO initialization. This is a remaining evidence gap, not an established
root cause.
