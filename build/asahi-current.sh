#!/usr/bin/env bash
# Build-only candidate: keep the deployed kernel/bootloader unchanged.
set -euo pipefail
repo=$(cd -- "$(dirname -- "$0")/.." && pwd)
work=${RUNNER_TEMP:?}/asahi-current-build
mkdir -p "$work" "$repo/artifacts"
exec > >(tee -a "$repo/artifacts/build.log") 2>&1
export LC_ALL=C ARCH=arm64 RUSTC=/usr/bin/rustc BINDGEN=/usr/bin/bindgen LIBCLANG_PATH=/usr/lib/llvm-21/lib
export KBUILD_BUILD_USER=kernel-builder KBUILD_BUILD_HOST=github-actions KBUILD_BUILD_VERSION=1
export KBUILD_BUILD_TIMESTAMP='Tue Nov 10 00:00:00 UTC 2026'
make() { command make LOCALVERSION= CC=gcc-15 HOSTCC=gcc-15 RUSTC=/usr/bin/rustc BINDGEN=/usr/bin/bindgen "$@"; }
base=1ed3045d3f7e92f4a8cf69c99e06c415857407c0
release=7.3.3-m1-usb4-rc1
printf 'Build-only candidate %s from Asahi %s\n' "$release" "$base"
git init "$work/linux"
git -C "$work/linux" remote add origin https://github.com/AsahiLinux/linux.git
git -C "$work/linux" fetch --depth=1 origin "$base"
git -C "$work/linux" checkout --detach FETCH_HEAD
git -C "$work/linux" config user.name 'Kernel Build Automation'
git -C "$work/linux" config user.email 'kernel-build@users.noreply.github.com'
git -C "$work/linux" show "$base:drivers/gpu/drm/apple/audio.c" > "$work/audio-before.c"
git -C "$work/linux" show "$base:drivers/gpu/drm/apple/av.c" > "$work/av-before.c"
python3 "$repo/consolidated/asahi-7.3.3-20261110/apply.py" "$work/linux"
python3 "$repo/consolidated/next-build/audio-open-lock/test-open.py" "$work/audio-before.c"
python3 "$repo/consolidated/next-build/hdmi-audio-lifecycle/test-lifecycle.py" "$work/av-before.c" "$work/linux/drivers/gpu/drm/apple/av.c" --output "$work/audio-lifecycle-tests"
cmp "$repo/consolidated/display-20261105/tests/dcp-route-policy.h" "$work/linux/drivers/gpu/drm/apple/dcp-route-policy.h"
python3 "$repo/consolidated/display-20261105/tests/test-policy.py"
python3 "$repo/consolidated/display-20261105/tests/test-integration.py" "$work/linux"
cp "$repo/consolidated/next-build/audio-open-lock/tests.json" "$repo/artifacts/audio-unlock-tests.json"
cp "$repo/consolidated/display-20261105/tests/policy-test-result.json" "$repo/artifacts/"
cd "$work/linux"
cp "$repo/build/running-kernel.config" .config
scripts/config --enable PCIE_APPLE_PCIEC --set-str LOCALVERSION '-m1-usb4-rc1' \
 --set-str SYSTEM_TRUSTED_KEYS '' --set-str SYSTEM_REVOCATION_KEYS ''
make olddefconfig
python3 "$repo/build/asahi-current-check-config.py" "$repo/build/running-kernel.config" .config "$work/linux" "$repo/artifacts/config-comparison.json"
cp .config "$repo/artifacts/kernel.config"
make -s kernelrelease | tee "$repo/artifacts/kernel-release.txt"
test "$(cat "$repo/artifacts/kernel-release.txt")" = "$release"
cp "$repo/consolidated/asahi-7.3.3-20261110/manifest.json" "$repo/artifacts/source-manifest.json"
git diff --check "$base"..HEAD
# Build the affected subsystems first to report porting errors early.
make -j2 drivers/gpu/drm/apple/ drivers/gpu/drm/amd/amdgpu/ drivers/thunderbolt/ drivers/pci/controller/ drivers/iommu/ drivers/usb/typec/tipd/ drivers/phy/apple/
make -j2 Image modules dtbs
stage="$work/stage"
mkdir -p "$stage/boot"
make -j2 INSTALL_MOD_PATH="$stage" INSTALL_MOD_STRIP=1 DEPMOD=depmod modules_install
make INSTALL_DTBS_PATH="$stage/boot/dtbs/$release" dtbs_install
cp arch/arm64/boot/Image "$stage/boot/Image-$release"
cp System.map "$stage/boot/System.map-$release"
cp .config "$stage/boot/config-$release"
cp Module.symvers "$repo/artifacts/Module.symvers"
rm -f "$stage/lib/modules/$release/build" "$stage/lib/modules/$release/source"
depmod -b "$stage" -e -F System.map "$release" 2> "$repo/artifacts/depmod-errors.txt"
test ! -s "$repo/artifacts/depmod-errors.txt"
find "$stage/lib/modules/$release" -type f -name '*.ko*' -print0 | xargs -0 -n1 modinfo -F vermagic | sort -u > "$repo/artifacts/vermagic.txt"
if grep -v "^$release " "$repo/artifacts/vermagic.txt"; then exit 1; fi
cp certs/signing_key.x509 "$repo/artifacts/module-signing-certificate.x509"
# Pinned v0.2 firmware already carries the new driver's configuration header.
bash "$repo/build/avd-firmware.sh" "$work/avd-firmware" "$stage" "$repo/artifacts"
cp -a "$repo/build/rootfs-supplements/usr" "$stage/"
mkdir -p "$stage/usr/share/doc/asahi-m1-usb4-rc1"
cp "$repo/consolidated/asahi-7.3.3-20261110/README.md" "$stage/usr/share/doc/asahi-m1-usb4-rc1/"
cp "$repo/initramfs/ubuntu/build-current-initramfs.sh" "$stage/usr/share/doc/asahi-m1-usb4-rc1/"
tar --zstd -cf "$repo/artifacts/linux-$release-arm64.tar.zst" -C "$stage" .
zstd -T2 -3 vmlinux -o "$repo/artifacts/vmlinux-$release.zst"
sha256sum "$repo/artifacts/"*.tar.zst "$repo/artifacts/"vmlinux-*.zst > "$repo/artifacts/SHA256SUMS"
printf 'Candidate built; source, config, module and DT compilation checks passed. Not installed or hardware tested. Matching initramfs requires target root-chain and firmware inventory.\n' > "$repo/artifacts/RESULT.txt"
