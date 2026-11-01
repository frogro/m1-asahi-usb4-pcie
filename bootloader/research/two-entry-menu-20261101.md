# Two-entry Asahi Linux menu, 2026-11-01

The user requested only Ubuntu Asahi and Googlebooks. Both installed EFI copies
load the canonical menu on the independent Asahi ESP (44FD-1525), with an
external configuration fallback. The original Apple Ubuntu entry, m1n1/U-Boot,
kernels and initramfs files are unchanged. All changed EFI/configuration files
were backed up before replacement and their new hashes verified after writing.
The backup directory is `/var/lib/asahi-two-entry-menu-20261101`, also copied
to the ThinkPad as `two-entry-menu/pre-menu-backup.tar`.

Ubuntu Asahi selects the external Samsung desktop when its boot filesystem is
readable. If its kernel/initramfs cannot be loaded, it tries the existing
internal Ubuntu symlinks. This is a load fallback, not an automatic recovery
from a later Linux hang. Original Apple Ubuntu remains the recovery choice.

Googlebooks keeps the original internal `/googlebook-reference-20261027`
Image/initrd and complete command line. Its OWC system partition is selected
by PARTUUID, not a variable Linux device name. Loading the bootstrap internally
is distinct from booting a USB4 OWC block device before Linux.

The OWC was verified through Dynabook USB hubs at 10000 Mb/s, with the expected
Googlebooks partition. The first hardware attempt stopped at the minimal GRUB prompt before OS loading.
QEMU reproduced the same failure: the standalone EFI could not read its embedded
`(memdisk)/boot/grub/grub.cfg` (outside-of-disk error), while the same menu loaded
from FAT worked. This is a GRUB packaging failure introduced by this menu update;
it does not establish a Googlebooks or dock problem.

The correction uses grub-mkimage with a directly embedded early configuration
invoking `normal` on the menu file. The early parser does not support normal-mode
`if` syntax, so the bootstrap uses simple commands. All required modules,
including gzio and efi_gop, are embedded. QEMU verified automatic menu display,
Ubuntu default, Googlebooks one-shot selection and consumption of next_entry.
No Android kernel boot was claimed from QEMU.

Both installed EFI copies were replaced and verified. The user moved OWC from
the dock to direct Mac USB-C; Linux confirmed USB UAS at 10000 Mb/s and the same
Googlebooks partition. A corrected one-shot boot was dispatched. The user initially reported the two-entry menu and Googlebooks visible. A
subsequent photo shows only kernel/bootstrap output, including AVD invalid
resource / -22 and DCP PIODMA child-device creation failures. Correct the
initial acceptance: menu display and kernel entry are confirmed; a functioning
Googlebooks graphical system is NOT confirmed. Googlebooks through the dock
remains untested. A comparison through the original Apple Ubuntu entry and
its unchanged Googlebook GRUB item is pending, with cabling kept unchanged.
There is no claimed Android automatic-return timer.
A guarded rollback helper and original files remain in the backup directory.

See the matching validation JSON for installed hashes and the separate
[deferred boot/kernel notes](deferred-boot-kernel-followups-20261101.md).
