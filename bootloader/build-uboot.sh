#!/usr/bin/env bash
# Build only. Never installs, mounts, repartitions or modifies the Mac.
set -euo pipefail
if [ "$#" -ne 2 ]; then
    echo "Usage: bash $0 /path/to/pinned-u-boot-source /path/to/new-build-dir" >&2
    exit 2
fi
src=$(realpath "$1")
out=$(realpath -m "$2")
profile_dir=$(cd -- "$(dirname -- "$0")" && pwd)
expected=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["uboot"]["commit"])' "$profile_dir/profile.json")
test "$(git -C "$src" rev-parse HEAD)" = "$expected" || {
    echo "Source commit does not match profile.json" >&2; exit 1;
}
test -z "$(git -C "$src" status --porcelain --untracked-files=no)" || {
    echo "Tracked source modifications found; use the pinned clean source" >&2; exit 1;
}
if [ -e "$out" ]; then
    echo "Use a new output directory; existing builds are not overwritten" >&2
    exit 1
fi
mkdir -p "$out"
cross=${CROSS_COMPILE:-aarch64-linux-gnu-}
jobs=${JOBS:-4}
make -C "$src" O="$out" CROSS_COMPILE="$cross" apple_m1_defconfig
cp "$out/.config" "$out/baseline.config"
"$src/scripts/config" --file "$out/.config" -e NVME_PCI -e CMD_BOOTMENU --set-val BOOTDELAY 10
make -C "$src" O="$out" CROSS_COMPILE="$cross" olddefconfig
python3 - "$out/.config" "$src/board/apple/mac/mac.env" <<'PY'
from pathlib import Path
import sys
config = set(Path(sys.argv[1]).read_text().splitlines())
required = ["NVME", "NVME_APPLE", "NVME_PCI", "PCIE_APPLE", "APPLE_DART",
            "USB", "USB_STORAGE", "USB_XHCI_DWC3", "CMD_NVME", "CMD_BOOTMENU",
            "BOOTMETH_EFILOADER"]
missing = [key for key in required if f"CONFIG_{key}=y" not in config]
if missing:
    raise SystemExit(f"Missing required boot functionality: {missing}")
if "boot_targets=nvme usb" not in Path(sys.argv[2]).read_text().splitlines():
    raise SystemExit("Internal NVMe/USB boot target policy changed")
PY
make -C "$src" O="$out" CROSS_COMPILE="$cross" -j"$jobs"
python3 - "$out" "$profile_dir/profile.json" <<'PY'
from pathlib import Path
import hashlib, json, sys
out = Path(sys.argv[1])
result = {"profile": json.loads(Path(sys.argv[2]).read_text()),
          "validation": "cross-build-only-no-hardware-test",
          "installed": False, "files": {}}
for name in ["u-boot-nodtb.bin", ".config"]:
    data = (out / name).read_bytes()
    result["files"][name] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
(out / "build-result.json").write_text(json.dumps(result, indent=2) + "\n")
print("Development image built. Thunderbolt tunnel setup is NOT implemented. Nothing installed.")
PY
