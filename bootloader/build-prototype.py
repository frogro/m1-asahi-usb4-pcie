#!/usr/bin/env python3
"""Apply the experimental U-Boot patches in a new worktree and test/build.

Builds only. Does not connect to a Mac, assemble a boot bundle, install files,
change a boot entry or expose a Thunderbolt boot feature.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess as sp


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Git checkout containing the pinned commit")
    parser.add_argument("output", type=Path, help="New, nonexistent output directory")
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error("--jobs must be positive")
    here = Path(__file__).resolve().parent
    manifest = json.loads((here / "prototype.json").read_text())
    pin = manifest["base_commit"]
    source, out = args.source.resolve(), args.output.resolve()
    actual = sp.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if actual != pin:
        raise SystemExit("Source HEAD is not the pinned base")
    if sp.check_output(["git", "-C", str(source), "status", "--porcelain", "--untracked-files=no"]):
        raise SystemExit("Use a clean source checkout; tracked edits are not accepted")
    for entry in manifest["patches"]:
        if sha(here / entry["file"]) != entry["sha256"]:
            raise SystemExit(f"Patch hash mismatch: {entry['file']}")
    out.mkdir(parents=True, exist_ok=False)
    work = out / "source"
    env = os.environ.copy()
    env["SOURCE_DATE_EPOCH"] = sp.check_output(
        ["git", "-C", str(source), "show", "-s", "--format=%ct", pin], text=True).strip()
    env["SDL_VIDEODRIVER"] = "dummy"
    cross = env.get("CROSS_COMPILE", "aarch64-linux-gnu-")
    # A native sandbox build must not inherit an AArch64 compiler setting.
    env.pop("CROSS_COMPILE", None)
    commands = []

    def run(argv, name, cwd=None, timeout=1200):
        commands.append({"argv": [str(x) for x in argv], "log": name})
        with (out / name).open("w") as log:
            sp.run([str(x) for x in argv], cwd=cwd or work, env=env,
                   stdout=log, stderr=sp.STDOUT, check=True, timeout=timeout)

    print("Create isolated worktree and verify patch application", flush=True)
    run(["git", "-C", source, "worktree", "add", "--detach", work, pin], "worktree.log", source)
    for index, entry in enumerate(manifest["patches"], 1):
        patch = here / entry["file"]
        run(["git", "apply", "--check", patch], f"patch-{index}-check.log")
        run(["git", "apply", patch], f"patch-{index}-apply.log")
    run(["git", "diff", "--check"], "diff-check.log")

    print("Build sandbox and execute DART, IOMMU, PCI, mailbox, USB4 packet and I2C tests", flush=True)
    sandbox = out / "sandbox"
    run(["make", f"O={sandbox}", "sandbox_defconfig"], "sandbox-config.log")
    run([work / "scripts/config", "--file", sandbox / ".config", "-e", "APPLE_DART", "-e", "APPLE_MBOX", "-e", "USB4_CFG_CODEC", "-e", "APPLE_I2C", "-e", "CMD_APPLE_CD321X"], "sandbox-enable.log")
    run(["make", f"O={sandbox}", "olddefconfig"], "sandbox-olddefconfig.log")
    run(["make", f"O={sandbox}", f"-j{args.jobs}"], "sandbox-build.log")
    tests = {}
    for pattern, expected in [("apple_dart*", 7), ("iommu*", 8), ("pci*", 14), ("apple_mbox*", 2), ("usb4_cfg*", 6), ("apple_i2c*", 6), ("cd321x*", 5)]:
        name = pattern.rstrip("*")
        log = f"test-{name}.log"
        run([sandbox / "u-boot", "-T", "-c", f"ut dm {pattern}"], log, sandbox, 60)
        text = (out / log).read_text()
        match = re.search(r"Tests run: (\d+),.*failures: (\d+)", text)
        if not match or tuple(map(int, match.groups())) != (expected, 0):
            raise SystemExit(f"Unexpected test result: {log}")
        tests[name] = {"tests": expected, "failures": 0, "live_and_flat_tree": name not in ("usb4_cfg", "apple_i2c", "cd321x")}

    print("Cross-build Apple M1 profile; preserve internal NVMe and USB", flush=True)
    apple = out / "apple"
    base = ["make", f"O={apple}", f"CROSS_COMPILE={cross}"]
    run(base + ["apple_m1_defconfig"], "apple-config.log")
    run([work / "scripts/config", "--file", apple / ".config", "-e", "NVME_PCI",
         "-e", "CMD_BOOTMENU", "-e", "USB4_CFG_CODEC", "-e", "DM_I2C", "-e", "APPLE_I2C", "-e", "CMD_I2C", "-e", "CMD_APPLE_CD321X", "--set-val", "BOOTDELAY", "10"], "apple-enable.log")
    run(base + ["olddefconfig"], "apple-olddefconfig.log")
    config = set((apple / ".config").read_text().splitlines())
    required = ["NVME", "NVME_APPLE", "NVME_PCI", "PCIE_APPLE", "APPLE_DART",
                "USB", "USB_STORAGE", "USB_XHCI_DWC3", "CMD_NVME", "CMD_BOOTMENU",
                "BOOTMETH_EFILOADER", "APPLE_MBOX", "USB4_CFG_CODEC", "DM_I2C", "APPLE_I2C", "CMD_I2C", "CMD_APPLE_CD321X", "APPLE_CD321X_STATUS"]
    if any(f"CONFIG_{key}=y" not in config for key in required):
        raise SystemExit("Required boot functionality missing")
    if "boot_targets=nvme usb" not in (work / "board/apple/mac/mac.env").read_text().splitlines():
        raise SystemExit("Boot targets changed")
    run(base + [f"-j{args.jobs}"], "apple-build.log")
    result = {"prototype": manifest, "tests": tests, "commands": commands,
              "installed": False, "hardware_validated": False,
              "thunderbolt_boot_implemented": False, "source_date_epoch": env["SOURCE_DATE_EPOCH"],
              "apple_image_sha256": sha(apple / "u-boot-nodtb.bin"),
              "apple_config_sha256": sha(apple / ".config"), "status": "software-validation-passed"}
    (out / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print("Software checks passed. No boot bundle installed; TB tunnel setup remains missing.")


if __name__ == "__main__":
    main()
