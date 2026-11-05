#!/usr/bin/env python3
from pathlib import Path
import json
import subprocess

w = Path(__file__).resolve().parent
shim = w / "test-include/linux"
shim.mkdir(parents=True, exist_ok=True)
(shim / "types.h").write_text("#include <stdint.h>\n#include <stdbool.h>\ntypedef uint64_t u64;\n")
subprocess.run([
    "gcc", "-std=gnu11", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
    "-fsanitize=address,undefined", "-I" + str(shim.parent),
    str(w / "test-policy.c"), "-o", str(w / "test-policy")
], check=True)
r = subprocess.run([str(w / "test-policy")], capture_output=True, text=True)
print(r.stdout + r.stderr, end="")
r.check_returncode()
(w / "policy-test-result.json").write_text(json.dumps({
    "result": r.stdout.strip(),
    "sanitizers": ["address", "undefined"],
    "scope": "draft policy implementation; serialized event interleavings, not real concurrency or hardware",
    "kernel_callbacks_connected": True,
    "hardware_tested": False,
}, indent=2) + "\n")
