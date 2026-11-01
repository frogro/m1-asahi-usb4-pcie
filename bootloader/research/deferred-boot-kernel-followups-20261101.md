# Deferred analysis: boot chain, Linux warnings, audio and wake display

Recorded at the user's request on 2026-11-01. The following remain scheduled
for a later focused analysis; successful USB4/USB3 boot acceptance does not
close them. Keep bootloader faults, Linux driver warnings and userspace
symptoms distinct. Do not suppress messages merely because enumeration works.

## U-Boot / GRUB before Linux handover

Revisit any pre-Linux failures against the exact installed bundle and EFI/menu
hashes. rc3 MP400 USB4 and independent USB3 starts passed; TB3 regression on
this latest integrated revision and broader enclosure coverage remain open.
The intermittent black return previously reached internal Linux and GDM;
it is not established as a pre-Linux boot failure, although retained hardware
state at handover remains a hypothesis requiring evidence.

The single `invalid environment block` was reported by `grub2-common` in
running Linux. Investigate GRUB configuration/storage management separately;
this does not prove that the pre-Linux GRUB executable failed.

## Linux kernel after U-Boot handover

Analyze the SIO late-IOMMU-probe and `__device_links_no_driver` warnings,
PCIe tunnel reset-release timeouts and `of_irq_parse_pci: failed with rc=-22`.
Retain ordering, boot IDs, hardware state and previous successful comparisons.
Do not label a symptom a kernel-only cause until boot-handover effects have
been excluded. No ACK-timeout suppression patch is requested.

## Already queued audio correction / WirePlumber shutdown

The candidate is [audio-open-lock](../../consolidated/next-build/audio-open-lock/README.md).
It is a DCP **kernel audio driver** correction, not a patch to WirePlumber.
`dcp_pcm_open()` can leave `data_lock` locked when `dcpaud_init_dma()` fails;
a subsequent open blocks. Probe89 recorded WirePlumber waiting at that mutex,
which explains the observed shutdown blockage on that path. The preceding
SIO failure and unavailable DMA channel remain a separate cause to investigate.

The corrected extracted function passed 13 cases with zero lock leaks, and an
ARM64 object build passed. It remains queued for the next kernel build, with
source/hash replay and a new release suffix; it is not in released egpu3.
Full kernel build and hardware failure/retry/shutdown validation are still due.
See also [Probe89 evidence](native-tb-grub-probe89-20261101.md).

## Screen black again after wake

Earlier sessions already investigated recovery: forcing HDMI on only restored
an image briefly; text VT3 remained visible; returning to the graphical
session subsequently restored a stable login screen. These observations point
to useful comparisons but are recovery actions, not proof of a permanent fix.
The local `usb-boot-20261030/hdmi-wake-references` archive contains the previous
mailing-list review, HDMI power/PMGR discussion and a community DCP candidate.
Its recorded conclusion found no matching validated native M1 HDMI-idle fix.

Revisit the exact earlier proposals and installed settings before changing
anything: distinguish a proper driver/state-ordering correction from disabling
idle/suspend, resetting an output or restarting a session. Test wake with the
normal desktop and power settings, including repeated cycles, and record
whether the fault is output power, DCP state, compositor/session or another
layer. Do not mark this closed because one VT switch recovered the picture.
