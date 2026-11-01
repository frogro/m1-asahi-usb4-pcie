#!/bin/sh
# Bounded test: authorize only the user-selected external root enclosure.
authorize_mp400_root() {
 case " $(cat /proc/cmdline) " in *' usb4diag=v19 '*) ;; *) return 0;; esac
 case " $(cat /proc/cmdline) " in *' root=UUID=1d4d5fd6-ea8a-4bb0-bf3c-2fc1f9e65935 '*) ;; *) return 0;; esac
 for d in /sys/bus/thunderbolt/devices/*; do
  [ -f "$d/authorized" ] || continue
  [ "$(cat "$d/vendor" 2>/dev/null)" = 0xb8 ] || continue
  [ "$(cat "$d/device" 2>/dev/null)" = 0x2463 ] || continue
  [ "$(cat "$d/unique_id" 2>/dev/null)" = 01544c17-5069-cb4f-ffff-ffffffffffff ] || continue
  case "$(readlink -f "$d")" in /sys/devices/platform/soc/501ac0000.cio/*) ;; *) continue;; esac
  [ "$(cat "$d/authorized")" = 0 ] || continue
  [ -e /run/mp400-root-authorization-attempted ] && continue
  : > /run/mp400-root-authorization-attempted
  /bin/sh /usr/lib/usb4-capture-v19.sh before-authorization
  if printf '1\n' > "$d/authorized"; then
   echo 'USB4 ROOT: selected MP400 enclosure authorized.'
  else
   echo 'USB4 ROOT: selected MP400 enclosure authorization failed.' >&2
  fi
  /bin/sh /usr/lib/usb4-capture-v19.sh after-authorization
 done
 return 0
}
authorize_mp400_root
