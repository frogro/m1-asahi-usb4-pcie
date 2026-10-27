#!/bin/sh
set -eu

# Destructive only to this uniquely named temporary file. Run only after a
# verified image of the FAT partition has been created outside the device.
disk=${DISK:-/dev/nvme1n1}
part=${PARTITION:-/dev/nvme1n1p1}
mount_dir=${MOUNT_DIR:-/mnt/apciec-write-test}
test_name=${TEST_NAME:-APCIEC-WRITE-TEST.bin}
backup=${BACKUP:?set BACKUP to the verified partition image}
backup_sha=${BACKUP_SHA:?set BACKUP_SHA to its expected SHA-256}

cleanup()
{
	if mountpoint -q "$mount_dir"; then
		umount "$mount_dir" || true
	fi
	blockdev --setro "$part" || true
	blockdev --setro "$disk" || true
}
trap cleanup EXIT HUP INT TERM

[ "$(blockdev --getro "$disk")" = 1 ]
[ "$(blockdev --getro "$part")" = 1 ]
! findmnt -rn -S "$part" >/dev/null
printf '%s  %s\n' "$backup_sha" "$backup" | sha256sum -c -

mkdir -p "$mount_dir"
blockdev --setrw "$disk"
blockdev --setrw "$part"
mount -t vfat -o rw,sync,nosuid,nodev,noexec "$part" "$mount_dir"
[ ! -e "$mount_dir/$test_name" ]
dd if=/dev/urandom of="$mount_dir/$test_name" bs=1M count=4 conv=fsync status=none
written_sha=$(sha256sum "$mount_dir/$test_name" | awk '{print $1}')
sync -f "$mount_dir/$test_name"
umount "$mount_dir"

blockdev --setro "$part"
blockdev --setro "$disk"
mount -t vfat -o ro,nosuid,nodev,noexec "$part" "$mount_dir"
read_sha=$(sha256sum "$mount_dir/$test_name" | awk '{print $1}')
[ "$read_sha" = "$written_sha" ]
umount "$mount_dir"

blockdev --setrw "$disk"
blockdev --setrw "$part"
mount -t vfat -o rw,sync,nosuid,nodev,noexec "$part" "$mount_dir"
rm -- "$mount_dir/$test_name"
sync -f "$mount_dir"
umount "$mount_dir"
blockdev --setro "$part"
blockdev --setro "$disk"

fsck.fat -n "$part"
mount -t vfat -o ro,nosuid,nodev,noexec "$part" "$mount_dir"
[ ! -e "$mount_dir/$test_name" ]
umount "$mount_dir"
rmdir "$mount_dir"

printf 'write_sha=%s\n' "$written_sha"
printf 'disk_ro=%s partition_ro=%s\n' \
	"$(blockdev --getro "$disk")" "$(blockdev --getro "$part")"
