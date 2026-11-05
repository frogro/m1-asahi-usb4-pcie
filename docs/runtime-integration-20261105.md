# Runtime integration — 5 November 2026

This branch brings the public build recipes up to the locally tested source
changes. It does not replace a boot-tested installation with an untested full
kernel or claim all historical hardware errors resolved.

| Component | Integrated source/build | Hardware status |
|---|---|---|
| U-Boot | All 17 patches through USB3 recovery, USB4 child router and common internal menu; pinned hashes, six CI profiles | Existing installed executable retained. Clean reconstructed source and M1 build pass; rebuilt binary not installed. |
| Ubuntu | 8 display/provider patches plus queued audio unlock after storage/eGPU base; new full-build version `7.2.12-usb4sd4-egpu4` | Permanent egpu3 module-overlay profile passed normal reboot, Samsung/Yotta root via Dynabook, graphical login and both connected monitors. Full egpu4 needs its own hardware run. |
| Googlebook | Separate Android build, existing audio unlock and selected-boot-router ancestor protection; version `7.2.12-googlebook-usb4-egpu2` | Earlier ancestor-guard runtime passed direct and Dynabook/Fanxiang GUI tests. This newly versioned full build is not installed or hardware-tested. WD currently absent. |
| Ubuntu initramfs/DT | Installed overlay hook, exact reproducible automatic display DT configuration, separate full-kernel rebuild instructions | New normal boot loaded the recorded replacement module hashes. Normal menu still offers Ubuntu, Googlebook and internal recovery. |
| Googlebook initramfs/vendor | Parameterized local bootstrap/preload sources and metadata-preserving local assembler; vendor removable-USB patch | Complete images, proprietary files and credentials remain local. USB-root disk exclusion is still required before applying the broad removable-disk rule to USB/SCSI-root profiles. |
| Mutter | Three source corrections, Debian symbol changes and repeatable source-package preparation in separate [PR #2](https://github.com/frogro/m1-asahi-usb4-pcie/pull/2) | Installed `50.1-0ubuntu2.5+asahi.hotplug3`; earlier eGPU hotplug, cursor and blank/wake checks passed. No full suspend claim. |

## Validation

- Clean pinned U-Boot reconstruction: every recorded source hash matches; M1
  build and all profile tests passed, including 74 actual scan-orchestration cases.
- Corrected a test that still read an absolute local xHCI source path; it now
  tests the supplied checkout. All 134 handoff assertions pass on that source.
- Ubuntu patch replay: all 18 display postimages byte-identical to built source;
  queued audio fix applies. Actual-function tests: 15 routing, 14 transport,
  15 consumer, 109 CD321x fault/transition cases; policy simulation 200000 events.
- Googlebook Android/audio/ancestor patches apply without fuzz. Ancestor guard:
  225 topology/authorization/parameter/reference assertions pass.
- Automatic DT rebuild is byte-identical to the installed DT:
  `1be8d33723849998598ec4a0dde441fb88e36aabd2aace26563fbb96b2263429`.
- Mutter source package replays all three corrections and Debian symbol changes.
  Earlier installed native build passed unit, monitor-config, monitor-dbus,
  monitor-scale and cursor-overlay tests.

## Deployment and rollback

The normal Ubuntu entry loads `/boot/initrd.usbc-auto` with the preserved
storage parameters and automatic display opt-in. Googlebook and internal
recovery menu bodies are unchanged. U-Boot/m1n1 executable payloads are unchanged
by this display installation. The new full builds are **build-only** outputs,
retained as draft artifacts; automatic installation or latest-release promotion
is not part of this change. Ubuntu and Android module ABIs must never be mixed.

The persistent Ubuntu rollback is
`/var/lib/asahi-display-routing/20261105-before/rollback.py`. Previous Image,
initramfs and root modules remain available. The separately registered legacy
Apple Googlebook boot environment is untouched.

## Explicitly remaining investigations

The initial PCIe tunnel-reset error -110 still occurs before a successful
root retry and remains separate from monitor routing. Other-port dock display,
rapid/simultaneous route competition, HPD IRQ and real system suspend are not
certified. Android automatic native/dock display routing is not ported by this
Ubuntu series. Earlier audio hum and full cross-OS eGPU rendering coverage are
not retrospectively marked fixed.

The per-view cursor correction already has GNOME MR5207. The runtime GPU-add
and link-status changes have local hardware evidence and repository review
material; upstream GNOME submission requires an authenticated GitLab account.
