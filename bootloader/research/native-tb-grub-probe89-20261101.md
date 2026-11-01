# Native TB boot through the independent Asahi Linux entry

Probe89 on 2026-11-01 booted the Samsung 970 EVO Plus in the Yottamaster TB3 enclosure, attached directly to M1 Mac mini port1. The user confirmed the GRUB menu containing Samsung, text-console and desktop entries. Kernel, initramfs, and root filesystem are on the external SSD. No SanDisk is required for this path.

The independent Apple registration uses the official installer and 13.5 firmware context. The released m1n1 binary is unchanged. The original Ubuntu entry remains the default fallback. Only the separate Asahi Linux ESP contains the experimental U-Boot bundle.

## Evidence

- Kernel `7.2.12-usb4sd4-egpu3`, release `kernel-build-41220334942-1`, archive SHA-256 `af1e4d965fc892b5b5fcd1f0bcaf72d8e5a997c700dfbe606b963b0ed03a118d`.
- Boot ID `4046d5b5-4aac-4566-bc79-0ce6aa82b8a2`.
- Root UUID `1d4d5fd6-ea8a-4bb0-bf3c-2fc1f9e65935`; boot filesystem UUID `e10cc27a-5892-4594-befa-2c74255c78cf`.
- GRUB is read from TB ESP `/EFI/CODEXTB/GRUB89.EFI`; its exact hash is checked before execution.
- Original reset-release timeout is still logged; the released kernel's retry subsequently binds the PCIe host and enumerates the SSD. The initramfs contains the enclosure authorization hook, but no manual host-reprobe helper.
- Two 64 MiB write/fsync/direct-read tests passed, one during desktop use. Eight complete direct reads of the kernel image matched its hash. Eighteen health samples retained a live NVMe and the same SSH executable hash.
- The user confirmed a correct, usable desktop. This is evidence for visible output, not a complete system acceptance test.

Logs, build scripts, hash manifests, source snapshot and detailed results reside in `/mnt/android-build/Codex/asahi-bootloader-20261031/tb-boot-probe89/`.

## Boundaries and next bootloader work

This remains a guarded single-device test implementation. It uses port1, one NVMe namespace, the known partition layout and UUIDs, fixed filenames, and exact image hashes. It is not yet a universal TB/USB4 boot implementation or a replacement installer.

Next bootloader work should preserve the passed bundle, then separate controller/tunnel discovery from the diagnostic command. Replace the fixed filesystem and image selection with normal U-Boot block/EFI discovery and a configurable GRUB path. Keep bounded timeouts, read-only boot access, and checked NVMe/NHI/ACIO/DART cleanup before Linux handoff. Verify absent-device fallback and ordinary internal/USB boot before widening to another enclosure or port.

## Separate runtime findings

Probe87 with egpu1 later suffered root I/O errors. Its filesystem was repaired offline, and egpu3 was installed alongside it. Probe89 has not reproduced those I/O failures in the observed interval; the changes do not isolate the original cause.

Probe89 also records an SIO firmware crash during Linux initialization and a subsequent DCP audio open lock leak blocking WirePlumber. YouTube playback fails. A small lock-release candidate passed extracted-function fault tests and ARM64 object compilation, but is not installed and is not proof of a fix for the preceding SIO failure. The origin of the SIO firmware failure is not classified: a boot-handoff or firmware-context problem remains possible. Per user direction, audio-driver work is parked while U-Boot/TB boot is evaluated.

The scheduled return and final installed-state verification are recorded separately in `result.json`; consult that file for the outcome rather than treating reboot initiation as successful recovery.

## Manual desktop restart

The scheduled reboot at 14:06:42 UTC blocked on the known audio mutex. The user restarted through Asahi Linux and selected Desktop. Boot ID `085a4fd8-1ba4-40cf-bf03-d009403ad266` uses the same egpu3 kernel and Probe89 bootloader. SIO binds successfully on this run; WirePlumber remains responsive, the direct HDMI PCM open/playback succeeds, and the user confirms YouTube video and sound. No audio patch or module replacement was installed. This distinguishes a successful current session from a permanent repair of the intermittent startup failure. Automatic return to internal Ubuntu was not validated by this run.

Read-only verification confirmed the original Ubuntu boot bundle and the baseline backup on the separate ESP still match `8ba8fc1d6eea83f2626860784d36a8ac5afc052110352b4ba64afdd3ce57fe60`; the installed separate candidate matches Probe89 `fac6b87ea60a1e0b6af493ba89b4e168f2fa0fcdc033f53e2e3087d98dab7faa`.
