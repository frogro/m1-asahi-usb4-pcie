# Android removable USB disk source

Live diagnosis: the SanDisk was enumerated as sda with three partitions, and Android UsbHostManager saw it, but `sm list-disks` was empty. The effective vendor fstab had no `voldmanaged` source.

This patch adds a USB/SCSI DEVPATH source, independent of USB bus numbers and hub depth. It does not match native PCIe/NVMe root storage, internal Apple NVMe, or device-mapper nodes. It is for the tested native-NVMe Googlebook boot profile. A Googlebook root carried by USB/SCSI would also match; automatic boot-disk exclusion for that profile requires further integration before this can be enabled there. No chipset or SanDisk ID is hardcoded.

Android's public volume implementation supports FAT/exFAT; the Ubuntu test stick's EFI and Linux GPT types are not normal public data partitions. Disk recognition is distinct from mounting those filesystems. Do not format or repartition the Ubuntu fallback to hide that distinction.

The local implementation changes only vendor fstab. No kernel, U-Boot, Android security policy or user partition change is required. It is not yet enabled in a generic release image. Hardware result: PASS Android boot_completed, user-confirmed GUI, and SanDisk listed by StorageManager with 123589361664 bytes. No public volume is mounted: the stick contains EFI and Linux GPT types, which the standard vold public-volume selection skips. The misleading unknown-table warning follows foundParts=false even though sgdisk read GPT successfully. Native NVMe root is absent from the removable disk list.
