# Asahi 7.3.3 M1 USB4 integration candidate

Target: `7.3.3-m1-usb4-rc1`, pinned Asahi release `asahi-7.3.3-1` at
`1ed3045d3f7e92f4a8cf69c99e06c415857407c0`. Build-only candidate. No deployment,
firmware flashing, boot-default change, Googlebook image rewrite or hardware
qualification is implied by compilation.

The integration replays the behavior of the repository's existing 29-patch
USB4/PCIe/display/suspend series, its 16 eGPU follow-ups, and the eight permanent
native/dock display-routing changes against the current Asahi release. The
original series retains attribution, commit messages and licensing. This is a
consolidated port, not a claim of original authorship of all these changes.
In particular the first non-posted AMDGPU adaptations derive from Joshua Warren's
linux-aurora work; see `../egpu179/PROVENANCE.txt` and its original patches.
AI assistance was used. No third-party endorsement or new DCO sign-off is claimed.

Specific integration decisions:

- Keep current Asahi DCP PIODMA probe/defer and teardown corrections. Retain our
  route retirement before releasing controller resources. Add a managed cleanup
  action so all later probe failures, including deferred route providers, release
  the PIODMA child. Explicit remove/shutdown cleanup remains idempotent.
- Keep upstream CD321x partner-identity lifetime fix and the DART remapped-stream
  handling while preserving our USB4 transition sequencing and stream operations.
- Keep native Apple topology notification in TB tunnel creation; do not re-add
  the old Ubuntu PCI-NHI delayed rescan which the new Asahi tree lacks.
- Move the local non-posted DMUB buffer/PSP restriction to the new
  `amdgpu_dm_dmub.c`, preserving upstream's GPU-generation-specific placement.
- Include the queued DCP DMA-error mutex unlock and HDMI audio-service lifecycle
  correction. The latter previously passed two hardware wake cycles for audio
  availability, but does not fix the separate delayed physical HDMI blackout.
- Preserve full-system suspend rejection while automatic/native DP is active.
  Keep HPD-IRQ and deeper power-loss recovery limitations explicit.
- Preserve the tested runtime PCI aperture and AMDGPU parameter requirements.
  Firmware/DT, root authorization and bootloader setup are separate parts of the
  complete installation; replacing only Image is unsupported.

`apply.py` requires a clean pinned source checkout, checks all patch and source
hashes, applies the integration, checks its postimages, and commits the result.
The new build profile is `ubuntu-current`. Existing Ubuntu and Googlebook build
profiles remain available. The configuration migration reports obsolete symbols
and fails on missing still-declared enabled features or required runtime/security
options. Canonical certificate-file paths are intentionally removed because this
is an Asahi source build; kernel modules retain the configured local build-time
signing rather than being presented as Canonical-signed binaries.

The full package includes Image, modules, DTBs, config, symbol map and pinned AVD
v0.2 firmware with the existing vector-layout correction. Rebuild the target's
initramfs against the new module directory and its own firmware/root-chain
configuration. Do not include the egpu3 binary overlay. Keep appledrm/amdgpu out
of early userspace and available after mounting the real root; this ordering was
required by the earlier egpu4 control experiment. No arbitrary fixed sleep is a
substitute for correct readiness.

Before selecting this candidate: verify a matched DT/boot bundle, source/config
and module hashes, initramfs driver/hook/firmware inventory, and a functioning old
boot entry. Then qualify cold boot/reboot, external-root direct I/O, native and
dock displays, hotplug, audio recovery, eGPU and supported power states separately.
The M1-only PCIe path is not validated on other Apple SoCs or arbitrary eGPUs.

Build qualification update: run 42785369138 passed configuration migration and
the affected-subsystem object compilation, then failed in the unrelated Tyr
(Mali CSF) Rust GPU driver with E0063 (missing GPUVM OpMapRequest fields). This
M1/AMDGPU candidate explicitly disables CONFIG_DRM_TYR; it does not change the
shared GPUVM API to accommodate hardware absent from the target. Asahi AGX and
AMDGPU remain required. Their object builds run before the full distro build.
