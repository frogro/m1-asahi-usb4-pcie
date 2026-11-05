# Ubuntu early userspace and display profile

Initramfs is early Linux userspace, not U-Boot or Mutter. Keep storage discovery,
root-chain authorization and matching modules together. Never use the Android
bootstrap or Googlebook modules in an Ubuntu initramfs.

The persistent 5 November installation keeps the released egpu3 Image and
original root modules, and appends a version/hash-pinned module overlay to its
existing storage initramfs. `99-display-overlay-egpu3.sh` is the exact installed
pre-pivot hook. It checks original root module hashes before binding the five
replacement modules, only with the explicit command line and matching DT marker.
It is a compatibility deployment for egpu3, not a universal new-kernel hook.

The new egpu4 kernel build integrates these sources directly. For that build,
regenerate initramfs using its own installed module directory and retain the
existing tested root-chain dracut hooks; do **not** carry forward the egpu3
binary overlay/hook. The normal dracut invocation must explicitly select the new
kernel release and a new output filename. Check `lsinitrd` for storage, USB4,
NVMe, CD321x, matching firmware and root-authorization hooks before installation.
Retain the old Image, initramfs and menu entry until the new build passes boot.

`configure-display-dt.py INPUT.dtb OUTPUT.dtb --sha256 INPUT_SHA256` applies the
M1 automatic native/dock display bindings to a hash-pinned common-menu DT. It
preserves boot commands, both PCIe storage descriptions, built-in HDMI and the
legacy single Googlebook provider. It refuses non-M1 input. DT packaging into
m1n1's bundle must preserve the m1n1 and U-Boot executable payloads and all
installation-specific ESP UUIDs. This script deliberately does not flash a
bundle or copy another machine's UUIDs.

Verified persistent egpu3 artifacts:

- boot bundle: `6c945ac788a5161184605785b2316406ed316bf9376555bcadd8262f0fc94d45`
- initramfs: `4d0eeb2acf7148f144cec89c8a1267987ce0b36c3a0ba5d0026efbc2941018fa`
- appledrm: `27aa07c54caf37576e87fdbb0d77e2396123a63ca078439534ac3b8985f60dc6`
- thunderbolt_apple: `d3d6358414df1f1b4d090dc635f4b24de520fea232d94aac7b76712976bfcc00`

Normal reboot passed on 5 November: Samsung/Yotta root behind Dynabook,
graphical target active, both monitors connected, replacement module hashes
verified. The initial PCIe -110 retry remains an independently tracked warning.
Rollback of this local installation is the saved
`/var/lib/asahi-display-routing/20261105-before/rollback.py`; it restores boot
bundle, menu and GRUB environment and does not reboot automatically.
