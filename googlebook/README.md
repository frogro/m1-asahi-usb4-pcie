# Googlebook Android host kernel on the Asahi USB4/eGPU base

Experimental build only. No deployment, bootloader changes or installer promotion.

Base: UbuntuAsahi/linux `f7734f4c91c0f47d9e762786968057bec99a0788` (7.2.12), followed by the repository's 29 storage/display/suspend patches and 16 eGPU patches. Configuration starts from the published `7.2.12-usb4sd4-egpu3` build. The Android fragment then enables the 59 early-boot/security/storage/VM requirements checked by `check-config.py`.

`0001-android-host-7.2.patch` ports the previously used Android host additions (dm-default-key, dm-bow, dm-user, incrementalfs, ashmem compatibility, UID statistics and frequency accounting). See source hashes in `android-provenance.json` and compatibility decisions in `port-decisions.json`. `quota2` is built against this exact kernel for Android netd. Its upstream URL and commit are recorded in its provenance file. `0002-apple-audio-lock.patch` carries the separately queued DMA-error unlock fix; it preserves the error return. Hardware error-path validation remains pending.

The reverted R87 GPU kernel experiment is excluded. The R88 Mesa import/unbind change belongs to the existing Android vendor userspace and is not replaced here. SELinux remains enabled; this does not bypass Play Protect or device attestation.

Outputs contain the kernel, DTBs, matching modules and diagnostics. Proprietary Android initramfs/vendor files and device firmware are not included in this source directory or uploaded by this build. The matching initramfs and module image are assembled locally from the user's existing system. The old 7.0.2 vendor_dlkm must not be used with this kernel. A separate per-boot module image and boot entry are required before installation so the old fallback remains usable.

Passing compilation is not proof of Android graphics, video decoding, VM, dock, GPU userspace or suspend compatibility. The existing Googlebook fallback is kept separately. The current `latest` Ubuntu/Fedora installer release is unaffected.
