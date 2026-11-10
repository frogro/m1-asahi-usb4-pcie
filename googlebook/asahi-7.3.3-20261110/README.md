# Googlebook on the Ubuntu rc2 source foundation

Target: `7.3.3-googlebook-usb4-rc2`, build-only candidate. Start from exactly the
Asahi base and integrated source tree used by Ubuntu rc2 recipe commit
`41f97ac7ddb03b65fd5b6691e87c70bb225abbdd`: Asahi
`1ed3045d3f7e92f4a8cf69c99e06c415857407c0`, consolidated M1 USB4/PCIe/display/eGPU
integration and rc2 Radeon accounting/offline-teardown fixes. Apply the Android
host additions only after both shared manifests pass. The legacy Googlebook
7.2.12 build profile remains separate.

The Android additions retain the provenance in `../android-provenance.json` and
`../port-decisions.json`: dm-default-key, dm-bow, dm-user, incrementalfs, ashmem
compatibility, UID accounting and CPU-frequency accounting. Also retain the
selected boot-router and ancestor deauthorization guard. The shared integration
already includes the Apple audio-lock fix; do not apply it a second time.

Port-specific changes:

- fscrypt now implements block I/O in `fs/crypto/block.c`, uses byte positions
  and `fscrypt_needs_contents_encryption()`. Keep the new implementation intact
  and add the dm-default-key skip flag and merge boundary checks at these paths.
  Never substitute the older inline_crypt.c implementation.
- blk_crypto_init_key now takes policy flags. dm-default-key passes
  BLK_CRYPTO_CFG_ALLOW_HW to preserve hardware use when available and the existing
  configured software fallback. This does not introduce plaintext fallback.
- Relocate UID Kconfig/Makefile additions without removing newer misc drivers.
- Preserve the new task IPI-mask cleanup while adding cpufreq task cleanup.
- Use the Ubuntu-current configuration seed plus the Android fragment, keep
  SELinux and AVB/verity/FEC requirements and build quota2 against this exact
  kernel. Tyr remains excluded for the same reviewed reason as Ubuntu rc2.

CI exports Image, modules, DTBs, config, manifests and open-source AVD firmware.
No Android system/vendor image, account data, ADB keys or local signing keys are
uploaded. Assemble matching Android module images and initramfs locally; a Ubuntu
Dracut image is not appropriate. The new AVD firmware must be reconciled with the
private firmware inventory. Existing Android graphics/media userspace needs its
own tests; Ubuntu success does not prove Android eGPU or decoding support.

The verified boot package must be regenerated and authorized using the existing
local workflow before installation. A new Image cannot be substituted beneath
old hashes/signatures. Preserve the known working Googlebook and Linux boot paths.
No Play Protect certification, rollback-protection change or Android green/locked
claim follows from this build. Installation is outside this build workflow.

Local validation: exact patch replay and all 57 source pre/postimage hashes
passed. The extracted fscrypt setup/merge functions pass 294 policy cases with
stub cryptographic operations (the upstream code without the Android additions
fails 102 Android-specific expectations). This checks flags, inode classes, key
identity and contiguous I/O boundaries, not cryptographic output or on-disk data.
The boot ancestor helper passes 225 topology/authorization/reference cases.
Full compilation and Android runtime validation are still required.
