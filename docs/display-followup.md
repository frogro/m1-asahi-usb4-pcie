# Display follow-up, 27 October 2026

After complete storage cleanup, the sleep/idle inhibitor was removed at 22:31:26 CET. DCP powered the display off at 22:31:28. At 22:32:01 the display powered on; at 22:32:03 `display HPD removed` / `connected:0` occurred, followed by `display HPD asserted` / `connected:1` at 22:32:04. Swap submissions were then swallowed because external display timing/power was disabled.

SSH, the display-manager service and the same Ubuntu boot remained active. This was not a reboot. The user reports similarity to the earlier Googlebook wake/black-screen issue. A shared DCP/HDMI resume mechanism is a hypothesis, not yet proven by a side-by-side log comparison. Raw local evidence: `post-test-display.log` beside the repository checkout. All temporary external PCIe modules had already been unloaded.

Next: align DCP power, HPD, modeset and compositor events with the saved Googlebook wake trace; test a bounded display off/on sequence while retaining SSH and recording the boot ID. Do not attribute a working kernel's black display to a system crash without checking reachability and uptime.

## Reproduced on the consolidated Yotta system, 31 October 2026

Kernel `7.2.12-usb4sd4-egpu1`, boot ID `2fd16211-678b-43c9-be1c-352641df7808`: no system suspend entry/exit occurred. GNOME display idle powered off the native HDMI DCP at uptime 373.99 s. Wake powered it on at 413.36 s; HPD removal/reassertion followed at 420.38/420.62 s. The connector reappeared with `valid_mode:0`, and firmware discarded swaps with its display power/timings disabled. DRM then reported flip/commit timeouts. SSH and the running Yotta root remained available. This reproduces the ordering documented above, without proving the underlying cause.

A brief VT3/VT2 switch restored the login screen only temporarily (user confirmed). Keeping VT3 active subsequently gave a stable visible console (user confirmed). The desktop session was preserved. Logs were saved locally under `usb-boot-20261030/hdmi-wake-20261031-kernel.log` and on Yotta under `/home/frogro/hdmi-wake-20261031/`. A temporary GNOME idle-delay change from 300 to 0 is a diagnostic mitigation, not a driver fix; the screen lock remains enabled.

Next isolation: distinguish the native HDMI hotplug/modeset recovery from compositor idle/lock handling, and compare with the existing kernel link-status BAD notification when `valid_mode` is false. Do not treat successful USB4/PCIe suspend tests as coverage of this display-idle recovery path.
