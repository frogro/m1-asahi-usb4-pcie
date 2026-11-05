# Ubuntu display source integration

Apply after the pinned 29 storage + 16 eGPU patches using `apply.py`. The eight
hash-verified patches reproduce the tested source exactly. The queued audio DMA
error-path unlock is appended once. The optional Ubuntu full build now uses
`7.2.12-usb4sd4-egpu4`; the base non-eGPU build is retained. New versioned full
builds are candidates and are not installed automatically.

1. Check CD321x mode-transition errors before reporting HPD.
2. Drain queued updates on failed probe/unwind.
3. Replay native display readiness/HPD at the correct lifecycle point.
4. Register DP-IN providers per controller.
5. Arbitrate the shared M1 display controller across native and dock routes.
6. Bound native withdraw using its observed firmware latency.
7. Quiesce USB before changing the shared pins to native DisplayPort.
8. Preserve the old Googlebook singleton provider with a separate Ubuntu opt-in.

Automatic routing requires the explicit DT bindings in
`../../initramfs/ubuntu/configure-display-dt.py` (from repository root:
`initramfs/ubuntu/configure-display-dt.py`). Compiling the code alone does not
silently reroute an existing installation. Existing storage topology is retained.

Normal persistent egpu3-overlay reboot passed, including Samsung root behind
Dynabook and both active monitors. Earlier native hotplug passed at both Mac
ports; native-to-dock-to-native display switching also passed. Mocked tests do
not replace hardware qualification: fast competing events, opposite-port dock
display, HPD IRQ, full-system suspend and new Googlebook display routing remain
unqualified. The PCIe -110 retry is not declared fixed by this series.
