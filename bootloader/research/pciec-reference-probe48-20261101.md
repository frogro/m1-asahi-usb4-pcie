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
