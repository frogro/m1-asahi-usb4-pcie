# Locally installed Mutter corrections

The four installed packages are 50.1-0ubuntu2.5+asahi.hotplug3. These are Ubuntu
userspace patches, not Linux kernel, Android, initramfs or U-Boot patches.

- 0001: runtime GPU registration must notify monitor topology after successful
  renderer/cursor setup. Local candidate, not submitted upstream.
- 0002: per-view software cursor visibility; adapted upstream MR5207 backport.
  See GNOME gnome-50 commit 4b852db14f1c8c882fbb7e58499ffe171c094d9d.
- 0003: connector link-status changes and active atomic modeset recovery.
  Local candidate, not submitted upstream.

Hashes and publication state: manifest.json. Package reproduction additionally
requires the Debian symbol/version adjustments and the existing arm64 package
build procedure; these source snapshots are not a new CI package pipeline.
See ../../../docs/runtime-repository-audit-20261105.md for the full audit.

## Reproduce the installed package set

Use Ubuntu source package `mutter 50.1-0ubuntu2.5` (extract with `dpkg-source -x`,
which applies the distro quilt series). Verify input SHA256:

- `mutter_50.1.orig.tar.xz`: `9344502ce473f788795f26b45f8b8ff53c0a36b867470d705a11a3ee0911021e`
- `mutter_50.1-0ubuntu2.5.debian.tar.xz`: `50d2d9f011972576ddc4467528c49601918e5a477aa6b3e8268b9d2bf86e7d06`

In a disposable Ubuntu resolute ARM64 build environment:

```sh
python3 prepare-source.py /build/mutter-50.1
cd /build/mutter-50.1
dpkg-buildpackage -us -uc -b
```

Install build dependencies with `apt-get build-dep` inside that environment.
The complete default test suite may require KVM/display hardware. The tested
headless subset used a private XDG_RUNTIME_DIR, dbus-run-session and software GL:

```sh
LIBGL_ALWAYS_SOFTWARE=1 GIO_USE_VFS=local GIO_USE_VOLUME_MONITOR=unix \
 dbus-run-session -- meson test -C obj-aarch64-linux-gnu --no-rebuild \
 --print-errorlogs --timeout-multiplier 3 unit monitor-config-tests \
 monitor-dbus-tests monitor-scale-tests cursor-overlay-tests
```

Do not silently skip failing checks. Package build and these five groups passed
for the installed local source. The source replay is separately checked when
publishing this recipe. New ABI symbols are included in patch 0004. Install the
matching `gir1.2-mutter-18`, `libmutter-18-0`, `mutter-common`, and
`mutter-common-bin` together after saving the previous packages. Re-login is
required. This is unrelated to the kernel or initramfs build.
