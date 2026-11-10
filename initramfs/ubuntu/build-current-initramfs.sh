#!/usr/bin/env bash
# Generate an additional initramfs only; never change boot selection or existing images.
set -euo pipefail
version=7.3.3-m1-usb4-rc1
stage=${1:?Usage: sudo bash build-current-initramfs.sh /absolute/extracted-package /absolute/new/initramfs-path}
out=${2:?Missing candidate initramfs output}
stage=$(realpath -e "$stage")
[[ "$out" = /* && ! -e "$out" ]]
test -d "$stage/lib/modules/$version"
for module in thunderbolt_apple nvme appledrm amdgpu; do
 actual=$(modinfo -b "$stage" -k "$version" -F vermagic "$module")
 [[ "$actual" == "$version "* ]]
done
# Root authorization must be supplied by this installation, not copied from another machine.
test -r /etc/asahi/authorize-root-chain.sh
test -r /etc/asahi/boot-root-chain.json
test -r /usr/lib/dracut/modules.d/99usb-test-fallback/reprobe-yotta-root.sh
test -d /usr/lib/dracut/modules.d/91asahi-root-chain || {
 echo 'Root-chain module must be inventoried and adapted for this installation before generating an image.' >&2
 exit 1
}
# Omit the old binary display overlay; the new modules contain these sources directly.
dracut --kver "$version" --kmoddir "$stage/lib/modules/$version" \
 --fwdir "$stage/usr/lib/firmware:/usr/lib/firmware" --no-hostonly --no-hostonly-cmdline \
 --add-drivers 'thunderbolt_apple nvme nvme_apple' --omit-drivers 'appledrm amdgpu' \
 --omit 'usb-test-fallback' \
 --include /usr/lib/dracut/modules.d/99usb-test-fallback/reprobe-yotta-root.sh \
 /var/lib/dracut/hooks/initqueue/settled/20-root-host-reprobe.sh "$out"
lsinitrd "$out" > "$out.inventory.txt"
if grep -Eq '(appledrm|amdgpu)\.ko|99-display-overlay-egpu3|native-hpd/|restore-boot.sh|boot-original.bin' "$out.inventory.txt"; then
 echo 'Unexpected early graphics driver or obsolete module overlay in candidate' >&2
 exit 1
fi
grep -Eq '(authorize-root-chain|asahi-root-chain)\.sh' "$out.inventory.txt"
grep -q "lib/modules/$version" "$out.inventory.txt"
sha256sum "$out" > "$out.sha256"
printf 'Candidate initramfs generated; boot selection unchanged: %s\n' "$out"
