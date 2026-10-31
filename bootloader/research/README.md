# Candidates outside the validated prototype

These files are **not** listed in `../prototype.json` and are not applied by the
bootloader build workflow, kernel workflow or installer.

## RTKit OSLOG address decoding

The existing U-Boot handler first shifts the OSLOG request before extracting
its address, and then overwrites that result using the ordinary endpoint's
unscaled address field. For firmware-supplied OSLOG buffers, the callback
therefore receives the page number rather than the byte address. The candidate
extracts the OSLOG field before shifting and removes the later overwrite.
The normal endpoint path retains its existing extraction.

The host reproducers contain the actual handler body with mocked mailbox and
allocation callbacks. Four firmware-address cases fail before the correction;
all eight cases pass afterwards, including ordinary endpoint addresses,
host-allocated replies and zero-size rejection. Reproduce with:

```sh
cc -O2 rtkit-oslog-before.c -o /tmp/rtkit-before
/tmp/rtkit-before  # expected exit 1, four failing cases
cc -O2 rtkit-oslog-candidate.c -o /tmp/rtkit-candidate
/tmp/rtkit-candidate  # expected exit 0
```

This establishes a decoding bug, not a failure observed in the Mac hardware
runs. It does not validate the complete RTKit handshake or ACIO SRAM mapping.
Probe5 subsequently passed the internal-NVMe hardware regression with this
candidate. The OSLOG-specific firmware request path was not instrumented, so
this does not prove that branch ran on hardware. The change remains separate
from the validated prototype series.

The complete M1 cross-build also passes with this candidate applied after the
eight prototype patches. Its binary/config hashes are recorded in the result;
the production-profile image was not installed. A separate diagnostic build
with the same correction ran only in RAM in probe5.

## M1 port-1 PHY diagnostic (Probe6–8)

`atc-m1-diagnostic-candidate.patch` applies after the eight prototype patches
and the separate RTKit OSLOG candidate. It is **not** in `prototype.json` or
any installer. It adds an explicit `atcm1 1 check|start` diagnostic command;
normal boot targets never call it. The command is restricted to J274 port 1
and its exact named resources. The debug port is untouched.

The sequence is derived from the attributed, hardware-tested M1 Linux ATCPHY
source. It validates all five calibration groups before writes, verifies the
selected xHCI controller is stopped, holds its power domain, rebuilds the PHY,
and uses bounded power and PIPE acknowledgement waits. No ACIO/NHI, external
storage or DMA is started. A full reset is required afterwards; this is not an
OS handover implementation.

| Hardware comparison | Result |
| --- | --- |
| Probe6: DWC3 held in reset throughout | Power/calibration completed; PIPE lock timed out |
| Probe7: add Linux's initial dummy-clock selection | Same timeout; PIPE ACK read `0x0` |
| Probe8: additionally release DWC3 reset and verify xHCI remains halted | PIPE lock/unlock and entire sequence passed twice with identical payload |

Probe8 observed xHCI command `0x0`, status `0x801` after reset release. The
controller was reset/clamped again after the successful PIPE sequence. The
internal-NVMe reference file had the expected hash before and after all three
runs. These comparisons support an initialization-order explanation for this
diagnostic timeout; they do not prove USB4 link training or NVMe access. This
is unrelated to the excluded Linux PCIe-C reset-ACK classifier.

The candidate passes 55 sandbox tests and the M1 cross-build. They include
malformed calibration rejection, both orientations and modes, bounded waits,
failure injection at every I/O operation, and refusal to continue when the
post-reset halt guard fails. Patch application checks pass. Checkpatch reports
zero errors and five style warnings; the candidate is not an upstream-ready
submission. Hardware coverage is USB4 orientation 0 on one M1 port only.

See the adjacent `atc-m1-result.json` and the numbered logs under `validation/`.

## M3 mailbox prerequisite (initial software stage)

`m3-mailbox-candidate.patch` adds `apple,m3-mailbox-v2` alongside the existing
ASC mailbox layout. It applies after the PHY research candidate above.
It remains outside the prototype manifest. Initially software-only, it was
subsequently exercised by the Probe9/Probe10 diagnostics described below.
The M1 build and 56 sandbox cases pass. Sandbox MMIO truncates 64-bit TX
writes, so eight additional cases exercise the exact production send/receive
functions with full-width mocked MMIO under ASan/UBSan. These are software
checks, not proof of ACIO firmware communication. The selected register layout
is derived from Asahi Linux commit a7c69b66c79296a8b51e1555ac887fa6de2d07be,
`drivers/soc/apple/mailbox.c`, with attribution retained in the candidate.

Those initial prerequisites were integrated for the bounded Probe9 diagnostic
below: checked power-domain ownership, PCIe-C/reset ordering, ACIO SRAM
translation and bounded RTKit startup.

## ACIO M3 readiness diagnostic (Probe9)

Apply `rtkit-bounded-phases-candidate.patch` and then
`acio-m1-readiness-candidate.patch` after the PHY and M3 mailbox candidates.
The changes are research only and are not in `prototype.json` or an installer.
The 18 changed files were reconstructed from the recorded patch sequence and
compared byte-for-byte with the build source.

`atcm1 1 acio` validates J274 port1 resources and cold ACIO power domains,
retains the halted DWC3/PHY state, pulses PCIe-C reset before activating ACIO,
checks every power-domain transition, deasserts the ACIO reset, and boots RTKit
through the M3 mailbox. Firmware buffers must lie completely within reserved
ACIO SRAM; the diagnostic never allocates host DMA buffers for firmware.
It requests AP-on, checks M3 readiness, and requests firmware sleep. Power is
held until a mandatory whole-machine reset. There is no OS handover here.

Both identical RAM-only Probe9 runs reported reset status `0x4`, successful
RTKit boot/AP-on, firmware state `0x01000000`, and successful firmware shutdown.
The internal-NVMe reference file matched before and after each run. NHI, DART,
PCIe tunnel initialization and external disk access were not performed.
The Linux PCIe-C reset-ACK classification patch remains excluded; these are
separate boot-time reset and firmware handshakes.

The build passed 57 sandbox tests. Separate sanitizer-enabled mocks cover
22 reset/SRAM cases, 12 RTKit phase cases and 21 production-sequence cases.
The RTKit change bounds whole transitions under unrelated incoming messages
and deduplicates endpoint-map entries, matching Linux's endpoint bitmap.
A ten-second phase budget is a diagnostic policy, not a timing guarantee for
all Apple coprocessors. Only M1 internal NVMe and ACIO were exercised here.

The standalone `acio-m1-sequence-test.c` and `rtkit-bounded-phases-test.c`
can be built with a host C compiler and `-fsanitize=address,undefined`.
They contain extracted production functions with mocked dependencies; they
do not emulate hardware or replace the numbered physical test results.

## NHI capacity read (Probe10)

`nhi-m1-readonly-candidate.patch` applies after the Probe9 research sequence.
`atcm1 1 nhi` also requires a disabled NHI node with the exact J274 port1
resource and reads HOP_COUNT once after M3 readiness. It accepts twelve rings,
matching the Linux device-tree IRQ pairs; it rejects zero, all-ones, and any
other count. It does not configure NHI, allocate DMA buffers or build a tunnel.

Both identical RAM-only runs returned `0xc` (12), completed firmware sleep,
matched the internal-NVMe reference hash before/after, and performed the planned
reset. The M1 and sandbox builds pass, with 57 sandbox cases and 25 extracted
production-sequence mock cases. All 18 changed source files reproduce exactly
from the patch chain. See `nhi-m1-patch-reproduction.json` and the Probe10 logs.
The boot-script footer `NO-NHI-OR-TUNNEL` means no NHI transport initialization;
the explicit `NHI-READONLY PASS` line records the capacity-register read.

The subsequent DART and first NHI DMA gates are recorded below.
See `nhi-dma-next-steps.md` for the remaining external-link work.


## Bounded DART and first host-router DMA (Probe11–16)

These remain research candidates, outside `prototype.json`, the kernel series,
installer and installed bootloader. Apply after the Probe10 chain in this order:

1. `dart-t8110-command-candidate.patch`
2. `dart-bounded-flush-candidate.patch`
3. `nhi-dart-map-candidate.patch` (final Probe14 state)
4. `nhi-tunables-candidate.patch` (Probe15)
5. `nhi-host-read-candidate.patch` (Probe16)

The reproduction JSON files record byte-for-byte comparisons with the source
used for the diagnostic builds. Payload SHA-256 values and individual results
are in `nhi-host-result.json`; hardware logs are under `../validation/`.

DART flushes have a 1 ms deadline and latch faults. Failed map/unmap/remove
paths retain uncertain allocations and page tables. Generic U-Boot unmap is
still void: arbitrary callers must not assume that a timed-out unmap permits
freeing their buffers. The new diagnostic checks the explicit fault status.
The separate T8110 register correction is software-tested only, not M1 proof
of M2 behavior.

Probe12 correctly refused inherited nonzero TCR state. Probe13 established
that all 16 TCR values were 0x80080. Probe14 accepts only zero or that observed
value, requires all 64 translation-table entries to be invalid and all NHI
rings stopped, and enables translation only for SID1. Its 32 KiB map/unmap
passed twice. Probe15 additionally applied 29 RC and 226 NHI calibration
triplets, with prevalidated register bounds, while rings remained disabled.

Probe16 transmitted one route-zero configuration read through control ring0
with a two-second response deadline. The response passed framing, sequence,
route and CRC validation: `200005ac 0001c71b 00000000 00000000`, response port 7.
One RX descriptor completed, TX completed, and ring-disable readbacks passed.
The DART error register contained 0x04020000 with its error-valid bit clear;
this is not a claim that the raw register was zero. Internal NVMe hashes
matched before/after; RTKit shutdown succeeded and Ubuntu returned automatically.

Even a successful ring-stop readback is not proof of drained DMA. All 64 KiB
of descriptors/data and their mappings remain allocated until mandatory reset.
No external router, PCIe tunnel or OWC disk access occurred. Safe OS handover
and actual external boot remain unimplemented. The first Probe11 fallback
stalled during Ubuntu early boot and needed manual restart; its second return
and the subsequent completed probes returned automatically. No cause is claimed
for that isolated fallback failure.

The latest M1 and sandbox builds pass. The 57 sandbox cases are supplemented
by extracted-production host mocks: 17 ring/codec, 111 preflight, 35 DART
lifecycle and 32 ACIO-sequence cases, plus 41 tunable and 16 DART cases.
The host C tests can be compiled individually with a C compiler, for example
`cc -O1 -g -fsanitize=address,undefined nhi-host-ring-test.c -o /tmp/nhi-ring-test`.
These mocks establish software behavior under injected failures, not hardware
coverage beyond the numbered logs. Passed hardware tests are not repeated
without a specific new reason.


## Combined host/link discovery (Probe17–19)

Apply `nhi-inventory-candidate.patch` after the Probe16 chain, followed by
`nhi-combined-link-candidate.patch`. These remain isolated M1 research patches.
Probe18 was prepared but never run; Probe19 combined its work with link stages.

Probe17 read seven capabilities but timed out on the first adapter read.
Probe19 enabled the host router with checked readback, read all seven adapters,
validated the DROM and lane pairing, unlocked ports 1/2 and wrote/read back
cable information 0x11 derived from the current CD321x snapshot. The lane
remained at state 7 (Linux TB_PORT_UNPLUGGED) for all ten polls. The external
router read was NOT attempted. Overall result: bounded timeout -110, incomplete.
Both internal NVMe hashes and firmware shutdown passed; Ubuntu returned
automatically and was verified over SSH.

See `nhi-combined-link-result.json`, the Probe19 UART log, source reproduction
records and the 69 production-code mock cases / 57 sandbox cases. The frozen
source retains stale host-only comments/messages about write scope; the actual
combined scope includes the checked port-unlock and cable writes described
above. No external-router writes or external disk access occurred.

Next compare full PHY status and unsolicited packet contents against Linux
link/event handling. RX count 42 versus TX count 37 indicates extra packets,
not a decoded diagnosis. DMA storage remains retained until mandatory reset.
PCIe tunnel setup, external NVMe reads and safe OS handover remain absent.
Discovery is intended to become generic; this diagnostic deliberately requires
the validated M1 host lane mapping and USB4 mode. No installed changes.


### Probe20: link-state and event observation

`nhi-link-observe-candidate.patch` follows Probe19. Its added reads found both
lanes in state7 and unchanged PHY control/mux/reset snapshots. The M3 mailbox
was empty before and after the NHI sequence. Five additional, CRC-valid packets
were identical EOF5 plug events for root port5 (the host DP-input adapter).
These do not establish a physical OWC connection. The root event was not
acknowledged by Probe20. Overall result remained timeout; the remote-router
read was not attempted. Internal hashes passed and Ubuntu returned by itself.
See the raw validation log and `nhi-link-observe-hardware.json`.

Next test adds Linux-style bounded root event acknowledgments. This is
separate from the excluded Linux PCIe reset-ACK classification patch.
No claim is made yet that missing event acknowledgments cause the link failure.


### Probe21: bounded root event acknowledgement

`nhi-event-ack-candidate.patch` follows Probe20. It adds the Linux
`tb_cfg_ack_plug` wire format to the codec and serializes one-way ACK packets
after the current TX descriptor completes. It accepts only CRC-valid, exactly
sized root-router events for ports1–7; at most eight acknowledgments and
63 total TX slots are permitted. The existing two-second TX and ten-second
transport deadlines remain. Other routes, malformed events and event floods
stop the diagnostic. No external router register write or disk access is added.

The 94 extracted-production host cases include exact plug/unplug wire values,
CRC/reserved-bit failures, wrong routes/ports, uncompleted ACK TX, DART faults
and notification floods. Sandbox57 and M1 build pass. On hardware, the ACKs for
root ports5/6 completed and the repeated port5 notifications stopped. Both
physical lanes nevertheless remained state7; the external router was not read.
Internal NVMe hashes and firmware shutdown passed, and Ubuntu returned by itself.
See `nhi-event-ack-result.json` and the Probe21 UART log. Event acknowledgment
is now hardware-tested, but it is not a demonstrated external-link fix.

The subsequent Linux comparison boot used unmodified Ubuntu package modules
for kernel7.2.0-1001-asahi-arm: the loaded srcversions matched the files, and
the files matched the package MD5 manifest. It was NOT the consolidated project
kernel. It reached CL0 on both lanes and discovered the OWC at4.888seconds,
then lost the link at15.583seconds with unchanged cables (user-confirmed).
A CD321x/ATC mux warning followed; the OWC subsequently appeared over USB.
This demonstrates initial link training, not a stable consolidated-kernel result.
The disconnect cause remains undetermined. The five-second Probe22 observation
is a bounded timing comparison, not an assumed repair.


### Probe22: bounded five-second link observation

Apply `nhi-link-window-candidate.patch` after Probe21. It changes only the
interval between the ten both-lane observations from100ms to500ms. No reset,
PHY values, cable data, ACK policy or descriptor limits change. The ten-second
transport deadline still bounds slow responses. Software coverage adds a link
that becomes ready after three seconds, verifies a permanently-unplugged lane
is observed for five seconds and preserves all previous injected failure cases.
95 production-code cases, 57 sandbox cases and the M1 build passed.
Hardware again showed both lanes in state7 for the full window. Type-C still
reported USB4 afterwards; a longer observation did not restore the link.
Internal hashes passed and Ubuntu returned automatically. See
`nhi-link-window-result.json` and the Probe22 UART log.

The user requested the saved working Linux path as the next live reference.
The installed 7.2.12-usb4sd4-egpu2 image, initramfs and config hashes were
checked against its manifest before arming its existing one-shot GRUB entry.
The initramfs restores the original boot bundle; a temporary seven-minute
return service bounds the live comparison. This release predates the native
prefetch/authorization-retry patches44/45; successful Test191 runtime evidence
is retained separately and must not be equated with a fully integrated boot.
