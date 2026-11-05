#!/bin/sh
native_hpd_overlay() {
case " $(cat /proc/cmdline) " in *" codex.auto_dp_route=1 "*) ;; *) return 0 ;; esac
profile=$(tr -d "\000" < /sys/firmware/devicetree/base/chosen/u-boot,integration)
[ "$profile" = "20261105-auto-dp-routing-rfc1" ] || return 0
[ -f /sysroot/usr/lib/modules/7.2.12-usb4sd4-egpu3/kernel/drivers/gpu/drm/apple/appledrm.ko ] || return 1
echo "d28f4c4730707fc56629e4c2d0b0e48c562fd58bbed8d00a7e9d5ebbbe192ca2  /sysroot/usr/lib/modules/7.2.12-usb4sd4-egpu3/kernel/drivers/gpu/drm/apple/appledrm.ko" | sha256sum -c - || return 1
[ -f /sysroot/usr/lib/modules/7.2.12-usb4sd4-egpu3/kernel/drivers/usb/typec/tipd/tps6598x-core.ko ] || return 1
echo "39ec76d1af9387d95c070ea377b654bba17fedb8f53aa819e9561120dc6e148a  /sysroot/usr/lib/modules/7.2.12-usb4sd4-egpu3/kernel/drivers/usb/typec/tipd/tps6598x-core.ko" | sha256sum -c - || return 1
[ -f /sysroot/usr/lib/modules/7.2.12-usb4sd4-egpu3/kernel/drivers/usb/typec/tipd/tps6598x.ko ] || return 1
echo "d25a1c0a4c51efdfddac92b99cb906905cb4cfc51e286b05ffb9db2c5c4d3a65  /sysroot/usr/lib/modules/7.2.12-usb4sd4-egpu3/kernel/drivers/usb/typec/tipd/tps6598x.ko" | sha256sum -c - || return 1
[ -f /sysroot/usr/lib/modules/7.2.12-usb4sd4-egpu3/kernel/drivers/usb/typec/tipd/sn201202x.ko ] || return 1
echo "fbe60fe8b220b794f08bce229019db98dbe5dcb5b63e508c65cdc8a9027c25dc  /sysroot/usr/lib/modules/7.2.12-usb4sd4-egpu3/kernel/drivers/usb/typec/tipd/sn201202x.ko" | sha256sum -c - || return 1
echo "87bd4d1285c38bcdd0e0725d86aac35ddfda93528e0572bb7271c09d74e97435  /sysroot/usr/lib/modules/7.2.12-usb4sd4-egpu3/kernel/drivers/thunderbolt/thunderbolt_apple.ko" | sha256sum -c - || return 1
mount --bind /native-hpd/thunderbolt_apple.ko /sysroot/usr/lib/modules/7.2.12-usb4sd4-egpu3/kernel/drivers/thunderbolt/thunderbolt_apple.ko || return 1
mount --bind /native-hpd/appledrm.ko /sysroot/usr/lib/modules/7.2.12-usb4sd4-egpu3/kernel/drivers/gpu/drm/apple/appledrm.ko || return 1
mount --bind /native-hpd/tps6598x-core.ko /sysroot/usr/lib/modules/7.2.12-usb4sd4-egpu3/kernel/drivers/usb/typec/tipd/tps6598x-core.ko || return 1
mount --bind /native-hpd/tps6598x.ko /sysroot/usr/lib/modules/7.2.12-usb4sd4-egpu3/kernel/drivers/usb/typec/tipd/tps6598x.ko || return 1
mount --bind /native-hpd/sn201202x.ko /sysroot/usr/lib/modules/7.2.12-usb4sd4-egpu3/kernel/drivers/usb/typec/tipd/sn201202x.ko || return 1
echo "AUTO-DP persistent overlays installed" > /dev/kmsg
}
native_hpd_overlay || echo "AUTO-DP persistent overlay failed" > /dev/kmsg
