#!/usr/bin/env bash
set -euo pipefail
repo=$(cd -- "$(dirname -- "$0")/.." && pwd)
work=${RUNNER_TEMP:?}/googlebook-full-kernel
mkdir -p "$work" "$repo/artifacts"
exec > >(tee -a "$repo/artifacts/build.log") 2>&1
export LC_ALL=C
export ARCH=arm64
export CC=gcc-15
export HOSTCC=gcc-15
export RUSTC=/usr/bin/rustc
export BINDGEN=/usr/bin/bindgen
export LIBCLANG_PATH=/usr/lib/llvm-21/lib
# Kernel Makefile assignments override environment-only tool selections.
make() { command make LOCALVERSION= CC=gcc-15 HOSTCC=gcc-15 RUSTC=/usr/bin/rustc BINDGEN=/usr/bin/bindgen "$@"; }
export KBUILD_BUILD_USER=kernel-builder
export KBUILD_BUILD_HOST=github-actions
export KBUILD_BUILD_TIMESTAMP='Sun Nov 1 00:00:00 UTC 2026'
export KBUILD_BUILD_VERSION=1
base=f7734f4c91c0f47d9e762786968057bec99a0788
printf '%s\n' "Build-only: no deployment, no bootloader changes" "Base: $base"
df -h "$work"
free -h
dpkg-query -W gcc-15 rustc rust-src bindgen libclang-21-dev pahole > "$repo/artifacts/toolchain.txt"
{
 uname -a
 gcc-15 --version
 /usr/bin/rustc --version
 /usr/bin/bindgen --version
} >> "$repo/artifacts/toolchain.txt"
git init "$work/linux"
git -C "$work/linux" remote add origin https://github.com/UbuntuAsahi/linux.git
git -C "$work/linux" fetch --depth=1 origin "$base"
git -C "$work/linux" checkout --detach FETCH_HEAD
git -C "$work/linux" config user.name 'Kernel Build Automation'
git -C "$work/linux" config user.email 'kernel-build@users.noreply.github.com'
python3 "$repo/consolidated/20261030/apply-to-checkout.py" "$work/linux" --apply
python3 "$repo/consolidated/egpu179/apply.py" "$work/linux"
revision=googlebook-usb4-egpu1
git -C "$work/linux" apply --check "$repo/googlebook/0001-android-host-7.2.patch"
git -C "$work/linux" apply "$repo/googlebook/0001-android-host-7.2.patch"
git -C "$work/linux" apply --check "$repo/googlebook/0002-apple-audio-lock.patch"
git -C "$work/linux" apply "$repo/googlebook/0002-apple-audio-lock.patch"
git -C "$work/linux" add .
git -C "$work/linux" commit -m 'Add Googlebook Android host requirements and queued Apple audio lock fix'
cp "$repo/googlebook/README.md" "$repo/artifacts/GOOGLEBOOK-LIMITS.md"
cp "$repo/googlebook/android-provenance.json" "$repo/artifacts/"
cp "$repo/googlebook/port-decisions.json" "$repo/artifacts/"
cd "$work/linux"
# Match the public certificate concatenation in debian/rules, including flavour overrides.
python3 - <<'CERTS'
from pathlib import Path
for kind,output in [('certs','canonical-certs.pem'),('revoked-certs','canonical-revoked-certs.pem')]:
 dirs=[Path('debian.asahi-arm')/kind,Path('debian')/kind]
 names=sorted({p.name for d in dirs for p in d.glob('*.pem')})
 assert names
 Path('debian',output).write_bytes(b''.join(next(d/n for d in dirs if (d/n).is_file()).read_bytes() for n in names))
CERTS
cp "$repo/googlebook/asahi-base.config" .config
scripts/kconfig/merge_config.sh -m .config "$repo/googlebook/android.fragment"
make olddefconfig
python3 "$repo/googlebook/check-config.py" .config > "$repo/artifacts/config-validation.json"
cp .config "$repo/artifacts/kernel.config"
cp "$repo/consolidated/20261030/config/tested-storage-boot-parameters.txt" "$repo/artifacts/"
cp "$repo/consolidated/20261030/config/tested-display-audio-options.txt" "$repo/artifacts/"
make -s kernelrelease | tee "$repo/artifacts/kernel-release.txt"
release=$(cat "$repo/artifacts/kernel-release.txt")
[[ "$release" == "7.2.12-$revision" ]]
git log --format=fuller "$base"..HEAD > "$repo/artifacts/applied-commits.txt"
git diff --check "$base"..HEAD
make -j2 Image modules dtbs
stage="$work/stage"
mkdir -p "$stage/boot"
make -j2 INSTALL_MOD_PATH="$stage" INSTALL_MOD_STRIP=1 DEPMOD=depmod modules_install
make INSTALL_DTBS_PATH="$stage/boot/dtbs/$release" dtbs_install
cp arch/arm64/boot/Image "$stage/boot/Image-$release"
cp System.map "$stage/boot/System.map-$release"
cp .config "$stage/boot/config-$release"
cp Module.symvers "$repo/artifacts/Module.symvers"
# Android netd uses quota2, absent from mainline. Compile against this exact build.
cp -a "$repo/googlebook/quota2" "$work/quota2"
make -j2 M="$work/quota2" modules
install -D -m644 "$work/quota2/xt_quota2.ko" "$stage/lib/modules/$release/extra/xt_quota2.ko"
# Build/source symlinks would point into an ephemeral runner.
rm -f "$stage/lib/modules/$release/build" "$stage/lib/modules/$release/source"
depmod -b "$stage" -e -F System.map "$release" 2> "$repo/artifacts/depmod-errors.txt"
if test -s "$repo/artifacts/depmod-errors.txt"; then
 cat "$repo/artifacts/depmod-errors.txt"
 exit 1
fi
find "$stage/lib/modules/$release" -type f -name '*.ko*' | sort > "$repo/artifacts/modules.txt"
test -s "$repo/artifacts/modules.txt"
find "$stage/lib/modules/$release" -type f -name '*.ko*' -print0 | xargs -0 -n1 modinfo -F vermagic | sort -u > "$repo/artifacts/vermagic.txt"
if grep -v "^$release " "$repo/artifacts/vermagic.txt"; then exit 1; fi
cp certs/signing_key.x509 "$repo/artifacts/module-signing-certificate.x509"
# Proprietary Android ramdisks, vendor images and device firmware are assembled locally.
# No Ubuntu user-space supplements belong in this Android host package.
# This exports a build result only; nothing writes to this machine's /boot or /lib/modules.
tar --zstd -cf "$repo/artifacts/linux-$release-arm64.tar.zst" -C "$stage" .
zstd -T2 -3 vmlinux -o "$repo/artifacts/vmlinux-$release.zst"
sha256sum "$repo/artifacts/"*.tar.zst "$repo/artifacts/"vmlinux-*.zst > "$repo/artifacts/SHA256SUMS"
printf 'Googlebook host kernel and module build checks passed. Not installed. Android initramfs/vendor module image must be assembled locally. Hardware validation pending.\n' > "$repo/artifacts/RESULT.txt"
