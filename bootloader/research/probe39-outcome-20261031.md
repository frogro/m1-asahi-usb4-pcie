# Probe39 hardware result and pending fallback recovery

m1n1 successfully started the U-Boot guest. The preserve-PHY core setup,
xHCI start and halt succeeded. Six USB DMA maps, both ports powered and
61/61 NHI control replies were observed. Firmware remained at Phase2;
no remote router, PCIe tunnel or external SSD IO. Both internal NVMe hashes
matched. Omitting the redundant late PHY reset alone did not solve the link.

The guest logged its planned reset. Ubuntu SSH has not returned and the user
reports black direct HDMI. Manual power-off/on into the regular Ubuntu entry
was requested; outcome pending. This is not classified as a failed m1n1-to-
U-Boot launch: the complete guest trace proves execution. The cause of the
subsequent missing Ubuntu return is not yet established. A previous boot
journal is needed if recovery permits. No installed boot files were modified.
Further hardware probes are paused pending recovery; no Probe40 is armed.

## Recovery follow-up

Ubuntu is reachable again after user intervention. The stock kernel and original boot.bin hash were verified; GRUB next_entry is empty. The previous persisted Linux boot reached graphical.target after 17.12 seconds and recorded a forced power-button shutdown at 17.66 seconds. Thus that boot reached userspace despite black HDMI. This does not establish successful automatic recovery from Probe39 or explain the black display. No new hardware probe is armed. Raw journals remain local.
