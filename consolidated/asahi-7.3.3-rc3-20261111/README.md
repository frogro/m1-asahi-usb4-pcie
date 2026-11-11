# M1 USB4 / Radeon rc3 — build candidate

This recipe builds **7.3.3-m1-usb4-rc3** from **asahi-7.3.3-2**, commit
`f6487a636f87bd4250f67f728b85077390811636`. It preserves the complete existing
M1 USB4/PCIe/eGPU/display integration and the rc2 VM-accounting and offline-DM
fixes. It does not install a kernel, modify boot selection or run hardware tests.
Ubuntu 7.2.12 remains the deployed fallback. Hardware validation is deferred by
owner request; this is not a claim that the warm-start failure is solved.

## Source review and integration decisions

The new Asahi base is 48 commits beyond our previous pinned base. Its changed
files do not intersect the files touched by the existing integration or rc2
patch. Both original patches still match every recorded preimage/postimage.
The new base includes the Asahi Tyr build repair, speaker IV-sense capture
repair, Apple NVMe changes and newer-device work. M1-specific benefit is not
assumed for changes aimed at other SoCs. Tyr remains disabled because it is a
Mali driver unrelated to this M1/Radeon setup, preserving the existing build
configuration; the former Tyr compilation error is no longer the justification.

`manifest.json` pins the base, original patch hashes, every patch's input/output
file hashes, the rebased rc2 tree, and the final tree. `apply.py` refuses a dirty
or different base and checks every stage. GitHub uses the same application and
regression tests as the local replay.

| Patch | Reason and boundaries |
| --- | --- |
| Original integration + rc2 | Preserve USB4 PCIe, native/tunnel display routing, Radeon/DART/TTM support, audio fixes, VM accounting and offline-device teardown. |
| 0003 UCSI init retry | Upstream retries EINVAL/ENODEV/EPROBE_DEFER while firmware becomes ready. It does **not** cover our ETIMEDOUT case. |
| 0004 CCG CAM bounds | Upstream rejects invalid alternate-mode indices and only translates successful completion data. |
| 0005 CCG read retry | Upstream permits four total attempts for EREMOTEIO, with three 1 ms waits. No write replay, no timeout replay. |
| 0006 UCSI debugfs length | Cap debugfs responses to the actual UCSI-version limit: 16 bytes for UCSI 1.x. The response structure alone is not the transport limit. |
| 0007 Asahi PR 503 | Take only head commit `87a2ad1c3428762076ce8e6dcbdd3579b275ec2e`, not the stale PR's entire diff. USB3 early setup, PIPE lock retry, override cleanup, DP mux teardown, host BIST change. This PR is open, not an accepted upstream guarantee. |
| 0008 AMD I2C count (local) | The AMD polling path returned zero on success, passed straight through `i2c_dw_xfer`. The I2C API requires the completed message count. Return `num_msgs`; preserve negative errors and runtime-PM cleanup. |
| 0009 CCG short transfers (local) | Reads require two completed messages; writes require one. A short nonnegative transfer becomes EIO rather than successful stale/partial data. Requires 0008 first for the AMD adapter. No short write is replayed. |
| 0010 UCSI debugfs NULL guard | Backport Bertrand Jacquin's reviewed proposal: power-level files return ENODEV while the asynchronous initializer has not published connectors. |
| 0011 AMD HDMI warning | Backport Paul Menzel's proposal: do not warn about the expected vendor-infoframe EINVAL when the sink has no HDMI-infoframe support. Does not change display programming or silence AVI failures. |
| 0012 Navi timeout retry (local candidate) | Exactly one extra PPM initialization attempt after ETIMEDOUT, delayed one second, only for PCI `1002:73a4` subsystem `1002:0408`. Disable for A/B testing with `ucsi_ccg.navi_init_retry=0`. It cannot reset the root-storage Thunderbolt controller. |
| 0013 ATC failure state (local) | Mark USB3/USB4 PIPE ready only after success, clear USB4 detection overrides if lock acquisition fails, reject unsupported USB3 PHY modes before powering hardware. Prevents a failed init from suppressing a later valid setup call. |

### Why the local UCSI retry is narrow

`ucsi_init()` can return an error even **after** publishing registered ports,
when the final CCI read fails. Re-entering initialization in that state can
replace/leak live connectors. The worker therefore refuses every retry once
`ucsi->connector` is set, including the new generic upstream retry paths.
Before publication, the existing init error paths unregister partial ports,
free the allocation and reset the PPM. The timeout flag allows only one extra
attempt; it does not reset on each deferred-work invocation.

Unregister cancels initialization work before freeing connectors. The patch
clears the freed connector pointer, because the CCG firmware-restart path
reuses the UCSI object, and register resets retry counters for that new
registration. Debugfs removal still precedes connector freeing.

This is a candidate for the observed early PPM timeout, **not** a proven fix
for the Radeon monitor's separate zero-sink DisplayPort bridge state. Nor is
it a CCG firmware reflash or full CCG stop/start. The existing generic retry
count remains bounded; no new unlimited polling is introduced.

### PR 503 limitations found in review

The PR's description mentions 150–688 ms readiness measurements, but its
actual ten 1 ms polls plus 5–10 ms backoffs nominally cover only about 60–110 ms
(excluding scheduling delays). We preserve that code rather than inventing a
longer delay without hardware evidence. Our USB4 shared-PHY retention and
local native-DP ownership code remain intact. The additional local patch fixes
error-state bookkeeping that the PR did not fix. Host BIST removal and early
USB3 setup still require testing with the real dock/root-drive topology.

## Verification

- Clean source replay checks every patch hash and pre/postimage and the final
  Git tree. Original rc1/rc2 files are not silently edited.
- Existing actual-C VM tests exercise 3,920 transitions before/after; the old
  code fails 2,384 transitions, the patched code has zero imbalances. Two DM
  teardown cases also pass after the fix.
- 557 new host cases compile **actual extracted C functions** for I2C success
  counts and errors, CCG partial/chunked transfers and retry limits, runtime-PM
  and allocation balance, UCSI retry bounds and post-registration failures,
  debugfs NULL handling, PHY success/failure state and override cleanup.
  Unpatched I2C-count and PHY-state code must fail the same assertions.
- These are mocked-I/O tests, not bus-timing, concurrency, monitor or suspend
  tests. ARM64 object compilation covers UCSI, AMD DesignWare and Apple ATC.
  The full GitHub build additionally compiles Image, modules and DTBs, audits
  config/security-driver preservation, runs existing audio/routing tests and
  verifies module vermagic/depmod output.
- 21 filesystem-model tests cover the optional recovery helper, including a
  DP partner arriving after 22 seconds, an already connected monitor, unknown
  bridge IDs, disappearing hardware and bounded failed recovery.

## Optional recovery helper, not automatically installed or enabled

`recovery/` is packaged under `/usr/share/doc/asahi-m1-usb4-rc3/`. Its service
and timer are examples for later explicit installation; package extraction
does not enable them. The helper allows **only rc3**, leaving the installed
7.2.12/rc2 helper unchanged. It waits up to 60 seconds for a Type-C port before
one client rebind, and for a late DP partner instead of the previous 10 seconds.
It exits without resetting if the display appears or hardware disappears.

It retains the measured bridge guard (identity `00e04c4470312e3400`, branch,
zero ports and zero sinks) before one Radeon UCSI connector reset. This acts
on the Radeon client only, never the Apple Thunderbolt root-storage port.
The 450-second service ceiling includes bounded discovery, a possible rebind,
partner wait and bounded child I/O; it is a worst-case limit, not a fixed delay.
Do not enable this timer alongside the previously installed recovery timer.
For a causal kernel A/B test, first observe the kernel without either helper.

## Remaining evidence gaps / deliberately not changed

- PCI tunnel reset-release and DesignWare-disable warnings are not suppressed.
  We do not yet have register-state evidence for a correct new reset sequence.
- GET_PDOS EINVAL does not justify globally hiding PDO support or skipping
  power negotiation. Record the failing command/role before adding a quirk.
- No new firmware was flashed. AVD firmware remains the existing pinned v0.2
  package used by the previous build; unrelated NVIDIA CCG firmware is unsafe
  to substitute for the Radeon controller.
- Monitor HDMI sleep behavior is separate from USB-C/DP negotiation.
- No claim of Googlebook compatibility, AVB status or Play certification from
  this Ubuntu build; Googlebook needs its own configuration and boot-image work.

## Build and later validation

Dispatch `.github/workflows/consolidated-kernel.yml` with `kernel_profile=ubuntu-rc3`
on this integration branch. Outputs go to a draft release with checksums; they
are not deployed. The matching `build-rc3-initramfs.sh` requires the target's
actual root-chain and firmware inventory before creating a separate initramfs.

Later hardware checks: two unchanged-cable warm starts; UCSI initialization
with the new quirk enabled/disabled; Radeon USB-C/HDMI plus dock display; eGPU
remove/reinsert; root-drive survival; suspend/resume. Record monotonic timestamps
for PPM readiness, DP partner discovery, bridge sink count and DRM activation.
Keep the known working kernel and boot path available throughout.

## Primary sources

- [Asahi 7.3.3-2](https://github.com/AsahiLinux/linux/tree/asahi-7.3.3-2)
- [Asahi PR 503](https://github.com/AsahiLinux/linux/pull/503)
- [UCSI initialization retry](https://github.com/torvalds/linux/commit/2542613815381e090d5036d5751ab5e2fd9f8b07)
- [CCG CAM bounds](https://github.com/torvalds/linux/commit/02ee864e8d2142c5648998944c3306ea6a763c26)
- [CCG read retry](https://github.com/torvalds/linux/commit/bbf6b99a57b2479bf51c3c8ad0946f4b8c33ed69)
- [UCSI debugfs guard and review](https://lkml.iu.edu/2610.3/03200.html)
- [AMD vendor-infoframe warning proposal and review](https://lore-kernel.gnuweeb.org/dri-devel/BN9PR12MB5146C1B694B96CDFDE3E3101F7602@BN9PR12MB5146.namprd12.prod.outlook.com/T/)
- I2C transfer return contract: pinned source `include/linux/i2c.h`, `struct i2c_algorithm` documentation.

Original upstream patch attribution is retained. Local patches and tests were
prepared with Codex; no maintainer review, upstream acceptance or DCO sign-off
is invented.
