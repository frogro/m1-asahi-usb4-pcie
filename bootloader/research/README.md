# Candidates outside the validated prototype

These files are **not** listed in `../prototype.json` and are not applied by the
bootloader build workflow, kernel workflow or installer.

## RTKit OSLOG address decoding

The existing U-Boot handler first shifts the OSLOG request before extracting
its address, and then overwrites that result using the ordinary endpoint's
unscaled address field. For firmware-supplied OSLOG buffers, the callback
therefore receives the page number rather than the byte address. The candidate
extracts the OSLOG field before shifting and removes the later overwrite.
The normal endpoint path retains its existing extraction.

The host reproducers contain the actual handler body with mocked mailbox and
allocation callbacks. Four firmware-address cases fail before the correction;
all eight cases pass afterwards, including ordinary endpoint addresses,
host-allocated replies and zero-size rejection. Reproduce with:

```sh
cc -O2 rtkit-oslog-before.c -o /tmp/rtkit-before
/tmp/rtkit-before  # expected exit 1, four failing cases
cc -O2 rtkit-oslog-candidate.c -o /tmp/rtkit-candidate
/tmp/rtkit-candidate  # expected exit 0
```

This establishes a decoding bug, not a failure observed in the Mac hardware
runs. It does not validate the complete RTKit handshake or ACIO SRAM mapping.
The candidate needs an internal-NVMe hardware regression test before promotion
into the prototype series, since the existing Apple NVMe driver also uses RTKit.

The complete M1 cross-build also passes with this candidate applied after the
eight prototype patches. Its binary/config hashes are recorded in the result;
that image has not been loaded on hardware or installed.
