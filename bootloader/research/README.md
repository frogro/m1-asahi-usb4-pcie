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

## M3 mailbox prerequisite (software only)

`m3-mailbox-candidate.patch` adds `apple,m3-mailbox-v2` alongside the existing
ASC mailbox layout. It applies after the PHY research candidate above.
It remains outside the prototype manifest and every hardware payload.
The M1 build and 56 sandbox cases pass. Sandbox MMIO truncates 64-bit TX
writes, so eight additional cases exercise the exact production send/receive
functions with full-width mocked MMIO under ASan/UBSan. These are software
checks, not proof of ACIO firmware communication. The selected register layout
is derived from Asahi Linux commit a7c69b66c79296a8b51e1555ac887fa6de2d07be,
`drivers/soc/apple/mailbox.c`, with attribution retained in the candidate.

Before hardware use, checked power-domain ownership, PCIe-C/reset ordering,
ACIO SRAM translation and bounded RTKit startup still need integration.
