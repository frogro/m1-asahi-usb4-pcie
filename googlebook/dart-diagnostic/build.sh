#!/usr/bin/env bash
set -euo pipefail
repo=$(cd -- "$(dirname -- "$0")/../.." && pwd)
work=${RUNNER_TEMP:?}/googlebook-dart-diagnostic
mkdir -p "$work" "$repo/artifacts"
exec > >(tee -a "$repo/artifacts/build.log") 2>&1
export LC_ALL=C ARCH=arm64 RUSTC=/usr/bin/rustc BINDGEN=/usr/bin/bindgen LIBCLANG_PATH=/usr/lib/llvm-21/lib
export KBUILD_BUILD_USER=kernel-builder KBUILD_BUILD_HOST=github-actions KBUILD_BUILD_VERSION=1
export KBUILD_BUILD_TIMESTAMP='Tue Nov 10 00:00:00 UTC 2026'
make() { command make LOCALVERSION= CC=gcc-15 HOSTCC=gcc-15 RUSTC=/usr/bin/rustc BINDGEN=/usr/bin/bindgen "$@"; }
base=1ed3045d3f7e92f4a8cf69c99e06c415857407c0
release=7.3.3-googlebook-usb4-rc2
gh release download kernel-build-42832041433-1 --repo frogro/m1-asahi-usb4-pcie -p Module.symvers -p kernel.config -D "$work"
git init "$work/linux"
git -C "$work/linux" remote add origin https://github.com/AsahiLinux/linux.git
git -C "$work/linux" fetch --depth=1 origin "$base"
git -C "$work/linux" checkout --detach FETCH_HEAD
git -C "$work/linux" config user.name 'Kernel Build Automation'
git -C "$work/linux" config user.email 'kernel-build@users.noreply.github.com'
python3 "$repo/consolidated/asahi-7.3.3-20261110/apply.py" "$work/linux"
python3 "$repo/consolidated/asahi-7.3.3-20261110/rc2/apply.py" "$work/linux" --before-dir "$work/rc2-before"
python3 "$repo/googlebook/asahi-7.3.3-20261110/apply.py" "$work/linux" --before-dir "$work/android-before"
cp "$work/kernel.config" "$work/linux/.config"
cd "$work/linux"
make olddefconfig
# Refuse unexpected configuration changes; compiler version strings may differ.
python3 "$repo/googlebook/dart-diagnostic/validate.py" config "$work/kernel.config" .config
make -j2 modules_prepare
cp "$work/Module.symvers" Module.symvers
test "$(make -s kernelrelease)" = "$release"
for variant in baseline candidate; do
 mkdir -p "$work/$variant"
 cp drivers/iommu/apple-dart.c "$work/$variant/apple-dart.c"
 printf 'obj-m += apple-dart.o\n' > "$work/$variant/Makefile"
done
python3 "$repo/googlebook/dart-diagnostic/validate.py" source "$work/baseline/apple-dart.c" "$repo/googlebook/dart-diagnostic/manifest.json"
git apply --check "$repo/googlebook/dart-diagnostic/legacy-locked-ttbr.patch"
git apply "$repo/googlebook/dart-diagnostic/legacy-locked-ttbr.patch"
cp drivers/iommu/apple-dart.c "$work/candidate/apple-dart.c"
for variant in baseline candidate; do
 make -j2 M="$work/$variant" modules
 aarch64-linux-gnu-strip --strip-debug "$work/$variant/apple-dart.ko" 2>/dev/null || strip --strip-debug "$work/$variant/apple-dart.ko"
 cp "$work/$variant/apple-dart.ko" "$repo/artifacts/apple-dart-$variant.ko"
done
python3 "$repo/googlebook/dart-diagnostic/validate.py" modules "$repo/artifacts" "$repo/googlebook/dart-diagnostic/manifest.json"
cp "$repo/googlebook/dart-diagnostic/manifest.json" "$repo/artifacts/dart-source-manifest.json"
cp "$repo/googlebook/dart-diagnostic/legacy-locked-ttbr.patch" "$repo/artifacts/"
cd "$repo/artifacts"
sha256sum apple-dart-*.ko > SHA256SUMS
printf 'DART-only diagnostic modules built against exact shipped Googlebook rc2 source/config/symbols. No installation or hardware result.\n' > RESULT.txt
