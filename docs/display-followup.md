# Display follow-up, 27 October 2026

After complete storage cleanup, the sleep/idle inhibitor was removed at 22:31:26 CET. DCP powered the display off at 22:31:28. At 22:32:01 the display powered on; at 22:32:03 `display HPD removed` / `connected:0` occurred, followed by `display HPD asserted` / `connected:1` at 22:32:04. Swap submissions were then swallowed because external display timing/power was disabled.

SSH, the display-manager service and the same Ubuntu boot remained active. This was not a reboot. The user reports similarity to the earlier Googlebook wake/black-screen issue. A shared DCP/HDMI resume mechanism is a hypothesis, not yet proven by a side-by-side log comparison. Raw local evidence: `post-test-display.log` beside the repository checkout. All temporary external PCIe modules had already been unloaded.

Next: align DCP power, HPD, modeset and compositor events with the saved Googlebook wake trace; test a bounded display off/on sequence while retaining SSH and recording the boot ID. Do not attribute a working kernel's black display to a system crash without checking reachability and uptime.
