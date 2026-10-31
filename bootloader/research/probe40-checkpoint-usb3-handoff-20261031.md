# Probe40 checkpoint and USB3-to-USB4 boot alternative

Recorded 2026-10-31. No new hardware probe is armed by this document.

## Probe40 checkpoint

Result and payload are preserved in commit b4217dc and the preceding
preparation commit 5b3a4a1. See [result](../validation/m1-probe40-result.json),
[analysis](tb-only-20261031.md) and [candidate patch](tb-only-candidate.patch).

The TB3-only policy held DWC3 in reset, omitted late PIPE/xHCI startup and
matched all 17 selected Linux PHY/PIPE controls. NHI completed 61 requests
and 61 replies, but the link remained in Phase2; no remote router or PCIe
tunnel was established. The five-second observation ended with -110.
DART error-valid was clear and internal read hashes matched. No external
SSD IO was performed. Ubuntu returned automatically, with the original
boot.bin hash and empty GRUB next_entry verified. Nothing was installed.

This removes one demonstrated controller-policy mismatch, not the remaining
link failure. Do not repeat Probe40 unchanged. Current cabling remains
debug cable beside Ethernet, TB3 Yottamaster on the other USB-C port, HDMI
directly to the Mac. OWC must be identified and connected explicitly before
any new experiment targeting it.

## Next steps for actual pre-GRUB Thunderbolt boot

1. Compare initialization order, calibration timing, sideband state and
   firmware setup with the working Linux trace. Matching a small set of
   steady-state registers is insufficient. Keep stock-kernel observations
   distinct from the audited downstream source and custom kernel builds.
2. Isolate a source-supported difference before preparing Probe41. Preserve
   bounded control transactions and RAM-only execution; do not add external
   SSD writes. Track the RTKit SLEEP-versus-poweroff cleanup difference
   separately, without attributing black HDMI to it without evidence.
3. After Phase3/Connected and remote-router reads succeed, discover actual
   adapters/resources, build the PCIe tunnel, enumerate NVMe and perform a
   read-only identity/hash comparison. Only then attempt GRUB/kernel loading.

## Separate alternative: USB3 boot, USB4 root filesystem

The user reports booting the OWC over a USB3 cable. OWC documents USB3.2
backward compatibility for Express 1M2. A suitable USB4 cable can carry
native USB3, but cable capability does not select the negotiated protocol.

Probe22 already recorded `USB4=1 TBT=0 USB3=0` and zero USB storage devices
during U-Boot's initial scan with OWC attached. Therefore simply running
`usb start` does not establish the proposed fallback in the observed state.

Proposed flow, not yet implemented or validated:

1. Establish native USB3 on the same USB4 cable before storage discovery.
   Determine a documented/reversible CD321x/PD and PHY policy; do not guess
   commands or assume resetting xHCI changes USB4 negotiation.
2. U-Boot/GRUB read the external drive over USB3 and load both kernel and
   complete initramfs into RAM.
3. Linux/initramfs quiesces USB storage, restores USB4 negotiation, establishes
   the PCIe tunnel and waits for the NVMe disk, before mounting root.
4. Identify root by verified filesystem UUID rather than sdX/nvme names.
   Confirm partition layout, logical sector size and read hashes agree
   through both transports. Do not mount the same filesystem through both.

The audited local Linux tipd/core.c already handles USB4/native-USB changes
by quiescing DWC3 before changing the PHY, even if the host role is unchanged.
That is useful existing work. It does not prove the controller can initiate
renegotiation from a boot-forced USB3 mode without a physical reconnect.
The relevant source is downstream HEAD
517fe27a2ce7fa8d03aa6705a10ff4422197ff5d; verify the eventual test binary
contains it rather than assuming equivalence with the stock kernel.

First experiment should prove USB3 enumeration and same-cable USB4 handover
with no mounted target volumes and read-only identity/hash checks. The OWC
contains backups: no formatting, repartitioning or installation is part of
this proposal. Define a bounded failure path before testing; do not switch
the transport underneath an active root filesystem. A later initramfs must
either establish the selected transport or stop/recover explicitly.

This could avoid implementing preboot PCIe tunneling for dual-mode OWC
enclosures. It would not solve booting TB-only Yottamaster hardware. The
existing internal Apple/m1n1 bootstrap remains necessary, while the kernel
and initramfs could remain on the external drive.

Sources: [OWC compatibility description](https://www.owc.com/blog/what-is-a-diy-drive-how-owcs-express-lineup-of-build-your-own-ssd-options-gives-you-more-control-over-your-storage),
[Asahi U-Boot boot flow](https://asahilinux.org/docs/sw/u-boot/),
the archived Probe22 UART log and the local downstream Linux source above.

## Clarification: suppress USB4 negotiation before boot

The requested policy is explicitly to prevent USB4 negotiation and select
native USB3 over the same cable, then permit USB4 under Linux. It is not
merely to ignore an already negotiated USB4 connection.

A subsequent source check found a material limitation: Sven Peter's
[CD321x mode-control patch, reviewed by Heikki Krogerus](https://lists.openwall.net/linux-kernel/2026/09/07/1667)
states that Apple's controller firmware selects alternate modes and Linux
cannot influence that selection. The local audited driver likewise sets
`cd321x_data.no_mode_control = true`. Its USB4/native-USB transition handling
reacts to firmware status; it is not a policy API to force that transition.

Consequently there is no established software switch in the examined driver
that implements the requested USB3-only boot policy. This does not prove a
preboot or firmware-specific mechanism impossible, but discovering such a
mechanism is a prerequisite, not an already available implementation step.
Commands documented for other TI TPS controller variants must not be assumed
compatible with Apple's CD321x firmware. No speculative PD-register writes
were made. Prioritize identifying an evidenced CD321x policy mechanism before
another hardware probe for this alternative.
