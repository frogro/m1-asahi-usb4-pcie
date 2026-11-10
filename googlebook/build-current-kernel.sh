#!/usr/bin/env bash
# Build-only candidate: keep the deployed kernel/bootloader unchanged.
set -euo pipefail
repo=$(cd -- "$(dirname -- "$0")/.." && pwd)
work=${RUNNER_TEMP:?}/googlebook-current-build
mkdir -p "$work" "$repo/artifacts"
exec > >(tee -a "$repo/artifacts/build.log") 2>&1
export LC_ALL=C ARCH=arm64 RUSTC=/usr/bin/rustc BINDGEN=/usr/bin/bindgen LIBCLANG_PATH=/usr/lib/llvm-21/lib
export KBUILD_BUILD_USER=kernel-builder KBUILD_BUILD_HOST=github-actions KBUILD_BUILD_VERSION=1
export KBUILD_BUILD_TIMESTAMP='Tue Nov 10 00:00:00 UTC 2026'
make() { command make LOCALVERSION= CC=gcc-15 HOSTCC=gcc-15 RUSTC=/usr/bin/rustc BINDGEN=/usr/bin/bindgen "$@"; }
base=1ed3045d3f7e92f4a8cf69c99e06c415857407c0
release=7.3.3-googlebook-usb4-rc2
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
python3 "$repo/consolidated/asahi-7.3.3-20261110/rc2/apply.py" "$work/linux" --before-dir "$work/rc2-before"
python3 "$repo/consolidated/asahi-7.3.3-20261110/rc2/test-regressions.py" "$work/rc2-before" "$work/linux" --output "$work/rc2-tests"
cp "$work/rc2-tests/results.json" "$repo/artifacts/rc2-regression-tests.json"
cp "$repo/consolidated/asahi-7.3.3-20261110/rc2/manifest.json" "$repo/artifacts/rc2-source-manifest.json"
python3 "$repo/googlebook/asahi-7.3.3-20261110/apply.py" "$work/linux" --before-dir "$work/android-before"
python3 "$repo/googlebook/asahi-7.3.3-20261110/test-fscrypt.py" "$work/linux" --before-dir "$work/android-before" --output "$work/fscrypt-tests"
python3 "$repo/googlebook/next-build/boot-storage-path/test-ancestors.py" "$work/linux/drivers/thunderbolt/switch.c" "$work/boot-guard-tests"
cp "$work/fscrypt-tests/results.json" "$repo/artifacts/android-fscrypt-tests.json"
cp "$repo/googlebook/asahi-7.3.3-20261110/manifest.json" "$repo/artifacts/android-source-manifest.json"
cp "$repo/googlebook/android-provenance.json" "$repo/artifacts/"
cp "$repo/googlebook/quota2/provenance.json" "$repo/artifacts/quota2-provenance.json"
python3 "$repo/consolidated/next-build/audio-open-lock/test-open.py" "$work/audio-before.c"
python3 "$repo/consolidated/next-build/hdmi-audio-lifecycle/test-lifecycle.py" "$work/av-before.c" "$work/linux/drivers/gpu/drm/apple/av.c" --output "$work/audio-lifecycle-tests"
cmp "$repo/consolidated/display-20261105/tests/dcp-route-policy.h" "$work/linux/drivers/gpu/drm/apple/dcp-route-policy.h"
python3 "$repo/consolidated/display-20261105/tests/test-policy.py"
python3 "$repo/consolidated/display-20261105/tests/test-integration.py" "$work/linux"
cp "$repo/consolidated/next-build/audio-open-lock/tests.json" "$repo/artifacts/audio-unlock-tests.json"
cp "$repo/consolidated/display-20261105/tests/policy-test-result.json" "$repo/artifacts/"
cd "$work/linux"
cp "$repo/build/running-kernel.config" .config
scripts/kconfig/merge_config.sh -m .config "$repo/googlebook/android-current.fragment"
# Tyr targets Mali CSF GPUs, not Apple AGX or the external Radeon. The pinned
# Asahi tree has a Tyr/GPUVM API mismatch; do not build this unrelated driver.
scripts/config --disable DRM_TYR --enable ANDROID_BINDER_IPC --enable ANDROID_BINDERFS --enable PCIE_APPLE_PCIEC --set-str LOCALVERSION '-googlebook-usb4-rc2' \
 --set-str SYSTEM_TRUSTED_KEYS '' --set-str SYSTEM_REVOCATION_KEYS ''
make olddefconfig
python3 "$repo/googlebook/check-config.py" .config --localversion=-googlebook-usb4-rc2 > "$repo/artifacts/android-config-validation.json"
python3 "$repo/build/asahi-current-check-config.py" "$repo/build/running-kernel.config" .config "$work/linux" "$repo/artifacts/config-comparison.json"
cp .config "$repo/artifacts/kernel.config"
make -s kernelrelease | tee "$repo/artifacts/kernel-release.txt"
test "$(cat "$repo/artifacts/kernel-release.txt")" = "$release"
cp "$repo/consolidated/asahi-7.3.3-20261110/manifest.json" "$repo/artifacts/source-manifest.json"
git diff --check "$base"..HEAD
# Compile Android additions first; report API-porting errors before a full build.
make -j2 block/ fs/crypto/ fs/incfs/ drivers/md/ drivers/cpufreq/ drivers/misc/uid_sys_stats.o mm/memfd-ashmem-shim.o kernel/fork.o kernel/exit.o kernel/profile.o kernel/sched/cputime.o fs/proc/base.o
# Build the affected shared subsystems next.
make -j2 drivers/gpu/drm/asahi/ drivers/gpu/drm/apple/ drivers/gpu/drm/amd/amdgpu/ drivers/thunderbolt/ drivers/pci/controller/ drivers/iommu/ drivers/usb/typec/tipd/ drivers/phy/apple/
make -j2 Image modules dtbs
cp -a "$repo/googlebook/quota2" "$work/quota2"
make -j2 M="$work/quota2" modules
stage="$work/stage"
mkdir -p "$stage/boot"
make -j2 INSTALL_MOD_PATH="$stage" INSTALL_MOD_STRIP=1 DEPMOD=depmod modules_install
make M="$work/quota2" INSTALL_MOD_PATH="$stage" INSTALL_MOD_STRIP=1 DEPMOD=depmod modules_install
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
# Keep Ubuntu services and Dracut recipes out of the Android package.
test -n "$(modinfo -b "$stage" -k "$release" -F vermagic xt_quota2)"
mkdir -p "$stage/usr/share/doc/googlebook-asahi-current"
cp "$repo/googlebook/asahi-7.3.3-20261110/README.md" "$stage/usr/share/doc/googlebook-asahi-current/"
cp "$repo/googlebook/asahi-7.3.3-20261110/manifest.json" "$stage/usr/share/doc/googlebook-asahi-current/"
tar --zstd -cf "$repo/artifacts/linux-$release-arm64.tar.zst" -C "$stage" .
zstd -T2 -3 vmlinux -o "$repo/artifacts/vmlinux-$release.zst"
sha256sum "$repo/artifacts/"*.tar.zst "$repo/artifacts/"vmlinux-*.zst > "$repo/artifacts/SHA256SUMS"
printf 'Googlebook candidate built on Ubuntu rc2 source foundation; Android config, source and module build checks passed. Not installed or hardware tested. Matching Android initramfs, module images and verified boot bundle must be assembled locally.\n' > "$repo/artifacts/RESULT.txt"
