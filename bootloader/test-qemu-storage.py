#!/usr/bin/env python3
"""Exercise generic NVMe/USB reads in QEMU; this is NOT an Apple USB4 test.

Only newly created regular files are used as emulated disks. No host block
device, Mac connection, firmware installation or partition operation on a
physical disk is performed.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pexpect


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def make_disk(out, efi):
    proof = out / "proof.bin"
    # More than two NVMe pages: exercises PRP lists and repeated read commands.
    data = bytes(range(256)) * 20480 + b"external-storage-proof\n"
    proof.write_bytes(data)
    disk, fat = out / "disk.img", out / "fat.img"
    with disk.open("wb") as f:
        f.truncate(96 * 1024**2)
    run("sfdisk", str(disk), input="label: gpt\nstart=2048,size=131072,type=U\n", text=True,
        stdout=subprocess.DEVNULL)
    with fat.open("wb") as f:
        f.truncate(64 * 1024**2)
    run("mkfs.vfat", "-F", "32", "-n", "UBOOT_TEST", str(fat), stdout=subprocess.DEVNULL)
    run("mcopy", "-i", str(fat), str(proof), "::proof.bin")
    run("mcopy", "-i", str(fat), str(efi), "::hello.efi")
    with disk.open("r+b") as dst, fat.open("rb") as src:
        dst.seek(2048 * 512)
        shutil.copyfileobj(src, dst)
    fat.unlink()
    return disk, hashlib.sha256(data).hexdigest(), len(data)


def exercise(out, firmware, disk, digest, length, storage):
    args = ["-machine", "virt", "-cpu", "cortex-a57", "-m", "512M",
            "-nographic", "-nic", "none", "-no-reboot", "-snapshot",
            "-bios", str(firmware), "-drive",
            f"file={disk},format=raw,if=none,id=testdisk"]
    if storage == "nvme":
        args += ["-device", "nvme,drive=testdisk,serial=UBOOT-TEST-NVME"]
    else:
        args += ["-device", "usb-ehci,id=ehci", "-device",
                 "usb-storage,drive=testdisk,bus=ehci.0"]
    transcript = out / f"qemu-{storage}.log"
    child = pexpect.spawn("qemu-system-aarch64", args, encoding="utf-8", timeout=45)
    results = []
    with transcript.open("w") as log:
        child.logfile = log
        try:
            child.expect(r"(?m)^=> ")

            def command(cmd):
                child.sendline(cmd)
                child.expect(r"(?m)^=> ")
                return child.before

            if storage == "usb":
                # No NVMe controller present: failure must return to the prompt.
                command("nvme scan")
                missing = command("nvme info")
                assert "QEMU NVMe" not in missing, missing
                results.append("missing-NVMe-returned-to-prompt")
                command("usb start")
            else:
                command("nvme scan")
            info = command(f"part list {storage} 0")
            assert "EFI" in info or "Partition" in info, info
            loaded = command(f"fatload {storage} 0:1 0x42000000 proof.bin")
            assert f"{length} bytes read" in loaded, loaded
            hashed = command("hash sha256 0x42000000 ${filesize}")
            assert digest in hashed, hashed
            results += ["GPT-and-FAT-readable", "multi-page-file-SHA256-matched"]
            loaded = command(f"fatload {storage} 0:1 0x43000000 hello.efi")
            assert "bytes read" in loaded, loaded
            hello = command("bootefi 0x43000000 ${fdtcontroladdr}")
            assert "Hello, world!" in hello, hello
            results.append("EFI-payload-loaded-from-emulated-disk-and-returned")
        finally:
            child.terminate(force=True)
    return {"storage": storage, "passed": results, "transcript": transcript.name}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--uboot", type=Path, required=True)
    p.add_argument("--efi-hello", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    disk, digest, length = make_disk(args.output, args.efi_hello.resolve())
    result = {"scope": "QEMU generic PCIe NVMe and USB storage only",
              "apple_usb4_tested": False, "installed": False,
              "firmware_sha256": hashlib.sha256(args.uboot.read_bytes()).hexdigest(),
              "proof_sha256": digest, "proof_bytes": length, "tests": []}
    for storage in ("nvme", "usb"):
        result["tests"].append(exercise(args.output, args.uboot.resolve(), disk.resolve(),
                                         digest, length, storage))
    result["status"] = "passed"
    (args.output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
