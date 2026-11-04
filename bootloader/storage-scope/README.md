# Storage-port scope for the M1 boot handover

This development profile reconstructs the November 2 transport/dock source and
the November 3 storage-port restriction used in the successful November 4
Googlebook comparison. It is separate from the older `integrated` default.
It does not install a bootloader or build a complete Googlebook image.

The controlled comparison reused the same U-Boot payload and m1n1 binary. Only
`bootcmd` (`tbboot recovery` to `tbboot`) and the target ESP changed. Initializing
only the storage controller before Linux allowed Googlebook to load its kernel
and initramfs from the WD in a directly connected Yotta and subsequently use the
Radeon connected to the other Mac port. Both displays were observed working.
Android userspace corrections were also required; U-Boot alone does not supply
those corrections.

## Build and source provenance

`manifest.json` pins upstream and every patch digest. Patches 1–12 retain the
repository's previous integration. Patch 13 reconciles the November 2 source
snapshot, including transport selection, inventory and dock routing. Patch 14
adds the explicit storage scope. The three scope source hashes match the saved
hardware candidate. The later experimental USB-address/reset retries from
November 4 are deliberately excluded: they did not establish a production fix.

```sh
python3 bootloader/storage-scope/build.py /path/to/asahi-u-boot /new/build-dir --jobs 4
```

The build requires the same cross compiler/dependencies as the integrated CI
job. It reconstructs the source from the upstream commit, checks the saved scope
hashes, executes the actual selection functions under ASan/UBSan, tests DTB
configuration and builds the Apple binary. The new deterministic build has a
different binary hash from the historical hardware candidate; source checks do
not make it a hardware-tested binary. See `validation.json`.

## Configure a storage scope

Use a matching integrated **U-Boot control DTB**, not the live Linux device tree:

```sh
python3 bootloader/storage-scope/configure-profile.py control.dtb storage.dtb \
  --port 0 --partuuid YOUR-STORAGE-ESP-PARTUUID
```

The output is a separate file. The command requires an explicit port and GPT
partition UUID. It does not infer the target from a volatile NVMe device number,
modify hardware nodes, package Apple boot assets or install anything.

For the tested J274 layout, port 0 is beside Ethernet and holds the Yotta;
port 1 holds the Razer and is left untouched for Linux. An excluded controller
is recorded as **excluded**, never as physically absent. Invalid masks, missing
targets, ambiguous UUIDs and inventory errors must fail rather than selecting an
unrelated disk. If the specified storage is absent, this scoped profile does not
promise an internal GRUB fallback; retain a separate Apple recovery boot entry.

The GRUB menu is independent of this early controller selection: it can offer
Ubuntu and Googlebook after the specified EFI loader has started. Kernel,
initramfs, module set and external-root configuration must agree. A normal menu
must not reference the bounded diagnostic initramfs or its timed reboot.

## Hardware coverage and limits

- Confirmed: direct Yotta on port 0, Razer on port 1, Googlebook kernel and
  initramfs loaded through Thunderbolt; both displays visible in short warm runs.
- Ubuntu control runs reached both displays and passed 30 GPU buffer copies.
  The external-root control loaded its kernel/initramfs internally; it is not
  evidence for every pre-Linux external boot configuration.
- Not established for this profile: swapped ports, arbitrary USB4 devices,
  downstream dock chains, eGPU hotplug, repeated cold starts or long stability.
- Earlier broader transport/dock tests remain separate evidence. Do not label
  this restricted success a universal Thunderbolt/USB4 bootloader release.

## Googlebook build policy

Complete Googlebook images are built and retained **locally only**. CI here may
compile/check U-Boot and existing kernel sources; it must not assemble or upload
Googlebook system/vendor/userdata images. Today's Mesa, HWC, Vulkan selection and
SELinux changes belong to the local Android image build. Re-running a kernel-only
workflow does not include them. Device-specific keys, network configuration and
private logs are not part of this public source update.
