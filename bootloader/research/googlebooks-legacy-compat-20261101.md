# Googlebooks legacy boot compatibility, 2026-11-01

The Googlebooks UI fails through both the current original Ubuntu boot chain
and integrated Asahi Linux rc3. Both reach the unchanged Googlebooks 7.0.2
kernel. The corrected two-entry GRUB itself works. The user requested a
bounded comparison against the previously working USB3 configuration.

## Evidence

Image, initramfs and original Ubuntu boot.bin exactly match the Oct31 recovery
manifest. This excludes file drift since that backup, but does not prove that
Oct31's boot stack still matched the earlier Android kernel. The Oct27 fresh
Googlebooks tests recorded an actual UI, ADB, graphics and decoder acceptance.
The subsequent clean Ubuntu installation regenerated m1n1/DT/U-Boot.

Current Ubuntu enumerates the OWC Express 1M2 as UAS at 10000 Mb/s, directly
connected to Mac USB-C. Its same USB -71 address error is followed by successful
SuperSpeed enumeration. The Googlebooks super PARTUUID and GPT disk identity
match the saved configuration. No conversion to TB storage is required for
this existing Googlebooks installation. No disk contents were repaired or
rewritten during this comparison.

Two source/device-tree incompatibilities were found:

* Current display DART providers use `#iommu-cells = <5>`, with address bounds
  in the consumer specifier. Googlebooks' 7.0 base `apple_dart_of_xlate()`
  explicitly rejects `args_count != 1`. The old tree uses one argument and
  `apple,dma-range` on the provider. The failed PIODMA IOMMU setup is consistent
  with that mismatch. Do not discard the additional cells blindly: they carry
  address-range information which must be preserved in a proper port. The
  actual initramfs apple-dart.ko was extracted and its argument-count check
  confirmed, rather than relying only on an unverified source/build match.
* The current `avd@269080000` node has register names code/sram/mbox/ctrl.
  The bundled legacy AVD driver first requests the absent piodma resource.
  The old tree had no AVD node and relied on Google's test-system runtime
  overlay. The visible -22 matches the missing-resource path. The exact
  overlay failure needs separate tracing if that implementation is retained.

## Controlled hardware comparison

The pre-reinstallation bundle was read from the OWC backup mounted read-only
with noload. SHA256: 28d7359550dfc4406625769f4ff85e06bcad5e5d9e09ac1d7ad74006ef40996c.
It was temporarily installed ONLY on the independent Asahi ESP. Original Apple
Ubuntu was untouched. Googlebooks Image/initrd, OWC cable and disk, corrected
GRUB EFI and menu were unchanged. The user confirmed **Googlebooks UI appears**.
This establishes a boot-stack/kernel compatibility regression, not a new-menu
or USB3-cable requirement failure. The whole old bundle was compared, so the
hardware result alone does not isolate every component to the DT.

Current integrated rc3 was backed up to
`/var/lib/googlebook-compat-20261101/integrated-before.bin`. A guarded service
restored it on original Ubuntu boot `ceb77101-0e53-4486-ade1-d164ecd00166`.
The rc3 hash, corrected EFI/menu hashes, original Ubuntu bundle and Googlebooks
kernel/initramfs hashes were rechecked. The restore service is now disabled.
Restoration verification is recorded in JSON.

## Permanent integration remains open

Do not globally downgrade the shared boot stack or claim the Googlebooks
entry works with rc3 yet. Preferred long-term work is to align the separate
Googlebooks kernel/drivers/firmware/DT bindings with the current boot stack,
then retest graphics, video and Android. A separately selected, matched legacy
boot stack is an alternative fallback. Changes must remain OS-specific so
Ubuntu USB3/TB/USB4 boot acceptance is preserved. This test added no kernel
patch and does not validate the OWC-through-dock Googlebooks path.
