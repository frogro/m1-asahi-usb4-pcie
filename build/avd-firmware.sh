#!/usr/bin/env bash
# Build the separate AVD firmware needed by CONFIG_VIDEO_APPLE_AVD.
set -euo pipefail
work=${1:?work directory}
stage=${2:?staging root}
artifacts=${3:?artifact directory}
commit=c870554fce20b9ee5ac46885c698d11e6a313948
mkdir -p "$work" "$stage" "$artifacts"
work=$(realpath "$work")
stage=$(realpath "$stage")
artifacts=$(realpath "$artifacts")
export PATH="/usr/lib/llvm-21/bin:$PATH"
git init "$work/source"
git -C "$work/source" remote add origin https://github.com/AsahiLinux/avd-fw.git
git -C "$work/source" fetch --depth=64 origin "$commit"
git -C "$work/source" checkout --detach FETCH_HEAD
git -C "$work/source" fetch origin refs/tags/v0.1:refs/tags/v0.1
test "$(git -C "$work/source" rev-parse HEAD)" = "$commit"
meson setup "$work/out" "$work/source" \
    --cross-file "$work/source/llvm.ini" --prefix=/usr \
    -Dvideo-codecs=all -Dc_link_args=-fuse-ld=lld
meson compile -C "$work/out"
DESTDIR="$work/package" meson install -C "$work/out"
python3 - "$work" "$commit" <<'PY'
import hashlib, json, pathlib, sys
work, commit = pathlib.Path(sys.argv[1]), sys.argv[2]
root = work / 'package'
fw = root / 'usr/lib/firmware/apple'
sizes = {'v2-t0': 0xc000, 'v3-t0': 0x10000, 'v3-t1': 0x10000,
         'v4-t0': 0x12000, 'v5-t0': 0x10000, 'v5-t1': 0x12000}
hashes = {}
for variant, size in sizes.items():
    p = fw / f'avd-fw-{variant}.bin'
    assert p.stat().st_size == size, str(p)
    p.chmod(0o644)
    hashes[p.name] = hashlib.sha256(p.read_bytes()).hexdigest()
doc = root / 'usr/share/doc/asahi-avd-firmware-local'
doc.mkdir(parents=True)
(doc / 'copyright').write_bytes((work / 'source/LICENSE').read_bytes())
(doc / 'build-manifest.json').write_text(json.dumps({
    'source': 'https://github.com/AsahiLinux/avd-fw', 'commit': commit,
    'codecs': 'all', 'files': hashes,
    'validation': 'Compiled and size/hash checked; decoding requires hardware testing.'
}, indent=2) + '\n')
PY
cp -a "$work/package/usr" "$stage/"
cp "$work/package/usr/share/doc/asahi-avd-firmware-local/build-manifest.json" "$artifacts/avd-firmware-manifest.json"
tar --zstd -cf "$artifacts/asahi-avd-firmware.tar.zst" -C "$work/package" .
mkdir "$work/package/DEBIAN"
cat > "$work/package/DEBIAN/control" <<'CONTROL'
Package: asahi-avd-firmware-local
Version: 0.1+git20261031.c870554-1
Architecture: all
Maintainer: Local Asahi test build <kernel-build@users.noreply.github.com>
Description: Apple video decoder firmware built from pinned AsahiLinux source
 Includes all six AVD hardware variants.
CONTROL
dpkg-deb --root-owner-group --build "$work/package" "$artifacts/asahi-avd-firmware-local.deb"
