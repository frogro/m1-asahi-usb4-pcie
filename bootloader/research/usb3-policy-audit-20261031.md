# USB3 policy audit for pre-GRUB boot

Status: 2026-10-31. This is an investigation, not an implemented boot feature.
See the [Probe40 checkpoint and cable comparison](probe40-checkpoint-usb3-handoff-20261031.md).

## Required distinction

The requested workaround needs native USB3 over a USB4-capable cable before
GRUB, followed by USB4/PCIe under Linux before root is mounted. Disabling a
PCIe tunnel inside an existing USB4 connection is a different operation.
USB3 tunneled through USB4 would also still require a working USB4 fabric.

## Evidence

* The paired cable test on `7.2.12-usb4sd4-egpu2` established native USB UAS at
  10 Gb/s and USB4 PCIe/NVMe access to the same OWC. Both returned the same
  first-64-MiB hash and 512-byte logical sectors. This does not demonstrate
  same-cable switching or preboot USB3 negotiation.
* The audited downstream Linux source is
  `517fe27a2ce7fa8d03aa6705a10ff4422197ff5d`. `tipd/core.c` declares
  `tipd_cd321x_data.no_mode_control = true`. The exposed TPS operations
  change data/power roles; they do not implement `enter_usb_mode` or
  `default_usb_mode_set`. The running Mac exposes data/power roles but no
  corresponding `usb_mode`/`usb_capability` selector in the inspected Type-C
  sysfs entries. Source findings and running-binary observations are kept
  separate; source HEAD alone is not binary provenance.
* [Sven Peter's CD321x patch](https://lists.openwall.net/linux-kernel/2026/09/06/453)
  explicitly describes autonomous firmware selection and marks mode control
  unavailable. The [earlier transition patch](https://www.spinics.net/lists/linux-usb/msg273671.html)
  describes reacting to controller notifications and coordinating the PHY
  with DWC3. Transition handling does not provide a policy selector.
* Generic Linux Type-C mode-selection sysfs support requires controller
  callbacks. It cannot supply missing CD321x commands. DWC3 `maximum-speed`
  controls the USB controller; it is not evidence of a PD Enter_USB veto.
* [Asahi USB-PD documentation](https://asahilinux.org/docs/hw/soc/usb-pd/)
  documents debug pin routing and a PD reset that disconnects and
  renegotiates. It does not document a force-native-USB3 action. Its debug
  USB action is USB2 and is not the OWC storage host path. Several actions
  remain unidentified; this is not proof that no undocumented mechanism
  could exist.
* [OWC's manual](https://eshop.macsales.com/manuals/owc-express-1m2-support-manual)
  provides no software mode-force procedure. Its physical switch controls
  LED brightness. Public ASMedia product information describes multiple
  transports but does not establish a compatible mode-force command.
* The recent Asahi PR listing and proposal descriptions in PRs
  [503](https://github.com/AsahiLinux/linux/pull/503),
  [515](https://github.com/AsahiLinux/linux/pull/515), and
  [660](https://github.com/AsahiLinux/linux/pull/660) did not establish a
  CD321x policy selector. PR503 describes PHY lock retries and teardown;
  PR515 describes keeping USB2 available when SS lanes serve DP; PR660's
  inspected diff fixes SPMI core linkage and error propagation. The first
  file-list pages for 503/515 contained unrelated base changes and were not
  treated as a complete implementation review. This was a targeted review,
  not an exhaustive claim about every historic branch. Direct lore access was unavailable;
  public mailing-list mirrors supplied the author-posted patches.

## User proposal: deny PCIe authorization

The [kernel documentation](https://docs.kernel.org/admin-guide/thunderbolt.html#de-authorizing-devices)
defines deauthorization as tearing down the PCIe tunnel. In the audited
software connection manager, `authorized_store` reaches
`tb_domain_disapprove_switch`, whose callback is `tb_disconnect_pci`.
That removes the PCIe tunnel and notifies the native PCIe topology. It does
not request CD321x PD renegotiation or select native USB3.

An enclosure-specific firmware reaction remains an empirical question.
Test it with the OWC unmounted, record the USB4 router and PD status as well
as USB storage topology, then reauthorize and verify a read hash. Losing
NVMe alone is not a positive result. A USB disk behind a USB4 tunnel is not
proof of native USB3 either.

`boltctl forget` removes a saved authorization record; it is not a USB-mode
selector or a substitute for inspecting the current kernel authorization.
Use a temporary sysfs deauthorization for this comparison rather than
deleting the user's enrollment. Check domain `deauthorization` support and
ensure automatic authorization does not invalidate the observation.

### Hardware comparison completed

The user returned the OWC to the USB4 cable. Its identity was verified in
sysfs and its NVMe was present on the custom kernel. Domain security was
`user`, with `deauthorization=1`. All OWC partitions were unmounted; root
remained on the internal SSD. A temporary timer provided a second path to
restore authorization; it was cancelled after successful restoration.

At 22:39:50 UTC, writing `authorized=0` removed the external NVMe. Five
samples over 20 seconds all showed authorization remaining zero, the USB4
router still present, and no USB mass-storage device. Thus automatic
reauthorization did not invalidate the observation. Writing `authorized=1`
at 22:40:10 UTC restored the NVMe. A direct 64-MiB read matched the previous
hash. The saved bolt enrollment was not deleted or changed.

**Result:** deauthorizing this already-connected OWC did not produce native
USB3 fallback during the observation window. This does not test initial
connection with authorization withheld from the outset, nor every enclosure
firmware or a longer timeout. It does refute using this particular observed
deauthorization operation as a working USB3 boot switch.

Local evidence: `usb3-policy-investigation/deauthorization-result.json`,
`deauthorization-post-read.json`, and the bounded experiment script. The
[public result summary](../validation/owc-deauthorization-20261031.json)
omits device UUIDs and partition details.

## Decision

No evidence-backed software USB3-forcing patch has been identified. Do not
guess TI commands across controller families, rewrite controller firmware,
or treat read-only status bits as policy registers. No such writes were
performed. Keep the USB3 cable solution distinct from the proposed same-cable
handover, and retain Probe40 as the checkpoint for actual preboot USB4/TB
development. A positive OWC authorization experiment would still need a
separate preboot implementation and Linux handover test.
