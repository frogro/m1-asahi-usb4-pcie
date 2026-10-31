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


### Probes23/24: S0 and root TMU separated

Probe23 read CD321x SYSTEM_POWER_STATE (0x20) before and after the unchanged
Probe22 transport. Both samples were S0 (value0). Both lanes remained state7;
there is no evidence from this initial state justifying an SSPS command.
Internal NVMe hashes passed and stock Ubuntu returned automatically.

`nhi-root-tmu-candidate.patch` follows Probe22 (Probe23 changed only the boot
script). Probe24 discovers the TMU capability, checks UCAP and initially clear
TD, sets TD, verifies it, programs LOWRES interval1000 with unrelated bits
preserved, verifies the interval, and clears/verifies TD. Failure after the
first attempted TD write runs bounded cleanup without masking the first error.
This adds nine normal transactions within the unchanged63-descriptor limit;
extra event headroom is consequently smaller and exhaustion fails closed.
M1 build, sandbox57,95 transport mocks and53 TMU fault-injection cases passed.

Hardware verified `LOWRES interval=1000 TD=0`, but both lanes stayed state7
through the five-second observation. Internal NVMe hashes passed, reset was
executed, and stock Ubuntu returned. Thus TMU parity is established, but it
is **not sufficient to establish the external link**. No external disk access,
remote-router write or installed bootloader change was performed. See
[m1-probe24-result.json](../validation/m1-probe24-result.json).

The saved Probe5 **runtime-exported** calibration arrays were also compared
with the working Linux DTB: all12 arrays (543 triplets) match byte-for-byte.
This uses the existing Probe5 capture, not a new Probe24 runtime dump; DROM
hardware identifiers are excluded from the published comparison.

The next isolated diagnostic enables bounded ACIO RTKit SYSLOG handling.
It is intended to expose firmware progress; no link-fix claim is made.


### Probe25: bounded ACIO SYSLOG

`nhi-acio-syslog-candidate.patch` follows Probe24. It opts only this ACIO
instance into SYSLOG endpoint2; normal RTKit clients retain their prior
behavior. The record layout follows Linux `drivers/soc/apple/rtkit.c`.
Firmware-provided buffer addresses must pass the existing SRAM range check.
The decoder rejects invalid indices, zero sizes and out-of-buffer records,
uses bounded byte reads, terminates strings and sanitizes control characters.
At most64 records are printed. Valid and rejected log notifications are ACKed;
receive-empty is distinguished from a transmit timeout, preserving real errors.

The diagnostic services at most8 mailbox messages per call,512 during the
NHI run, with existing RTKit/NHI deadlines and63 descriptors retained. No
new reset, PHY write, remote-router write or external disk I/O is added.
Transport/DART buffers remain retained until the mandatory full reset as
before. This tests firmware visibility, not a presumed firmware deadlock.

M1 build,57 sandbox cases,95 extracted-production transport cases and27
RTKit cases pass. The latter include6912 index/size/buffer combinations and
address/undefined-behavior sanitizers. Exact application of the incremental
patch reproduces all five changed source files. Hardware produced the expected SYSLOG initialization and five serviced
messages during NHI. The firmware version and lane-init parameters match the
successful Linux capture. It reached Phase1 and Phase2 but not Phase3 or
Connected in the observation window; both lanes remained state7. No decoder
rejections occurred. Internal hashes and RTKit shutdown passed; stock Ubuntu
returned. See [Probe25 evidence](../validation/m1-probe25-result.json).
Firmware phase numbers are observations, not reverse-engineered meanings.
The next comparison changes only the physical connection starting state:
a fresh OWC disconnect/reconnect after xHCI quiesce, before PHY/ACIO setup.


### Probe26: fresh connection after xHCI quiesce

`nhi-fresh-cable-candidate.patch` follows Probe25. The explicit `fresh` command
runs the existing resource preflight and halts only the selected xHCI. Before
PHY/ACIO initialization it waits at most120 seconds for a read-only CD321x
snapshot to show disconnect and then a USB4/TBT data connection. An unchanged
connection cannot satisfy this test. Transport errors abort; only transient
snapshot inconsistency (`EAGAIN`) is retried within the window. Newly read
mode/orientation/cable data are revalidated by the existing configuration path.
No PHY/ACIO/NHI initialization sequence is changed. This distinguishes a stale
partner starting state from missing host setup; it is not an acceptable final
requirement to physically reconnect a boot disk on every boot.

M1 build,57 sandbox cases and14 extracted-production cases with ASan/UBSan
passed. Tests cover absent disconnect, absent reconnect, USB-only state,
ambiguous modes, changing snapshots, I2C errors and the full wait deadline.
Hardware observed both detach and reconnect. Firmware again reached Phase2 only;
both lanes remained unplugged. Internal hashes and shutdown passed, and stock
Ubuntu returned. A fresh cable transition alone does not fix link establishment.
See [Probe26 evidence](../validation/m1-probe26-result.json).
The host240-second runner timeout and guest's
software reset remain recovery aids, not a hardware-hang recovery guarantee.


### Live Linux PHY register comparison after Probe26

A one-shot boot of `7.2.12-usb4sd4-egpu2` reproduced initial link loss. After
a physical OWC reconnect, Linux exposed the external router with two lanes
at 20 Gb/s each and the external NVMe. The normal internal boot bundle had
already been restored by the initramfs; a bounded return service was active.
A read-only allowlist captured 17 PHY/PIPE registers, guarding every read
with the associated active power-domain state and live router presence.
All 17 values exactly match Probe26, despite their different link outcomes.
This rules out a mismatch in these final values, not in all hardware state
or in initialization order. No external SSD writes were performed.
See [register comparison](../validation/probe26-linux-phy-register-comparison.json).

The next useful diagnostic compares the timing/order around ACIO readiness,
RC/NHI initialization and cable-info submission. Any extra register capture
must first establish that reads are safe and meaningful. No blind PHY writes
or PD resets are justified by the current evidence.


### Probe27: buffered initialization timing

`nhi-init-timing-candidate.patch` follows Probe26. A fixed 64-entry RAM buffer
records millisecond timestamps around PHY setup, ACIO power/reset and RTKit
readiness, RC/NHI tunables, DART probe, control-ring start, lane unlock and cable
information submission. It records at most the first eight consumed RTKit
messages. No allocation or added console output occurs while collecting the
trace; it is printed after the observation and shutdown return. Existing console
logging remains, so the experiment is not a measurement without observer effects.
A full buffer drops further records and reports their number without extra timer
reads. No PHY/reset/tunnel writes, timeouts or transport limits change.

This run uses the existing `host` command as in Probe25, without another physical
reconnect. It measures host execution and message-consumption times, not the time
a firmware event was generated. The successful Linux packet capture provides
a comparable NHI-control-to-cable interval and cable-to-first-remote-request
interval; it does not provide all earlier PHY transition timestamps.

M1 build, 57 sandbox checks, 95 production transport mock cases and three
trace-buffer checks (empty, timer wrap/order and 10,000 overflowing records)
passed. Buffer and transport checks used ASan/UBSan. The incremental patch
reproduces all five changed files. Hardware result is pending.

Probe27 hardware recorded 27 timestamps with no overflow. PHY setup took 2 ms;
PHY return to M3 start took 42 ms, M3 start to firmware-ready poll return 16 ms,
and firmware-ready to NHI rings 86 ms. Ring start to cable submission took
276 ms. The saved Linux capture spans 6.477 ms from its first control request
to cable submission; these starting points are not precisely identical.
U-Boot remained in Phase2 throughout the following 5.158 seconds, with no
remote-router response. Internal NVMe hashes and reset passed. See
[Probe27 timing](../validation/m1-probe27-result.json).

The bounded next counterprobe removes only successful per-packet console
printing from the NHI transport. The buffered timestamps, error reports, event
ACKs, register writes, waits and limits remain. This tests diagnostic overhead
as a cause; it is not yet a demonstrated fix.

### Probe28 result and deeper Phase2 source audit

Removing successful per-packet logging reduced ring-start-to-cable submission
from 276 to 146 ms. The link nevertheless stayed in Phase2 for the bounded
5.081-second observation; no remote router was read. Internal NVMe checks and
reset passed, and stock Ubuntu returned. See [Probe28](../validation/m1-probe28-result.json).

The [31 October source audit](phase2-source-audit-20261031.md) compares current
Asahi helpers, the local Linux call chain, all pre-cable control writes in the
working Linux trace, and mailing-list discussions. It identifies a previously
missed interleaving: Linux configures core PHY before ACIO, but selects USB4
PIPE only after ACIO/NHI/cable setup. The previous prototype selected PIPE
before ACIO. Twenty-five relevant upstream PHY helpers match the reference.

`nhi-late-pipe-candidate.patch` is the separate Probe29 comparison on top of
Probe28. The old monolithic PHY entry point retains its exact writes; only the
full host diagnostic uses the split and a one-use post-cable callback. All
59 sandbox tests, 97 ASan/UBSan transport mock cases and the M1 build pass.
The split tests verify write-for-write equivalence and fail-stop behavior at
every PIPE access. Transport tests cover callback order, single-use and error
cleanup. Hardware results are recorded below; no installation or external SSD writes.

`nhi-calibration-noop-candidate.patch` is another source-parity candidate saved
separately. It is not included in Probe29. Linux skips unchanged calibration
writes; the prototype does not. The extracted-source comparison (12 cases)
used that candidate and found only a remaining extra 10-us delay and redundant
PIPE lock clear within the PHY sequence. `compare-phy-sources.py` can regenerate
this comparison from the stated Linux checkout and candidate U-Boot sources;
its fake-MMIO results do not validate analog hardware or inter-driver timing.

Probe29 hardware: late PIPE configuration succeeded, but both lanes remained
in state 7 and Phase2. All 61 control requests had replies; internal NVMe
hashes and reset passed. This excludes the reordered PIPE step as a sufficient
fix in this test, not every possible timing dependency.
See [Probe29 result](../validation/m1-probe29-result.json).

Probe30 added `nhi-late-pipe-calibration-candidate.patch` on Probe29. The M1
build, 60 sandbox tests and 45 calibration fault cases passed. Hardware skipped
94 unchanged RC/NHI values but still stopped at Phase2; all 61 control requests
were answered. Stock Ubuntu returned, internal NVMe hashes matched and the
installed boot bundle is unchanged. See [Probe30](../validation/m1-probe30-result.json).
Next compare DWC3 core/PHY suspend state with working Linux; do not infer a
working TB boot path from these partial initialization results.

### Probe31: DWC3 register comparison

A fresh 7.2.12-usb4sd4-egpu2 Linux capture with the OWC linked over USB4
(two lanes, 20 Gb/s each) supplies the DWC3 reference. Probe31 adds read-only
controller snapshots to Probe30. M1 build, patch reconstruction and the
45-read snapshot fixture passed. Probe31 confirmed a lost host role and missing
CIO controls. Probe32 restored those controls, but Phase2 still stalled. Both
runs returned to stock Ubuntu with matching internal NVMe hashes. See
[DWC3 comparison](dwc3-core-comparison-20261031.md). This is diagnostic
instrumentation, not a link fix or an enabled xHCI DMA path.
