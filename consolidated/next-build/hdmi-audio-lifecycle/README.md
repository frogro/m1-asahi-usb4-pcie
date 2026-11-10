# HDMI audio service lifecycle candidate, 6 November 2026

This candidate fixes stale audio-open bookkeeping after a native HDMI firmware
video/audio service replacement. It is queued separately and is **not** part of
the normal kernel build or boot profile yet. Two native HDMI wake cycles passed the audio-availability check on the M1 Mac mini; see validation.json.

The source-level replay reproduces five failing lifecycle scenarios on the
unmodified av.c; all eight scenarios pass on the candidate. The harness executes
the actual lifecycle C functions with mocked firmware callbacks and ALSA events.
It does not emulate real kernel scheduling, DMA, or firmware.

Apply the patch to a disposable checkout of the consolidated egpu4 source.
Keep copies of the before/after av.c and run:

```sh
python3 test-lifecycle.py /path/to/before/av.c /path/to/after/av.c --output /tmp/av-lifecycle-tests
```

The existing audio DMA-error unlock must remain applied. The locally rebuilt
baseline .text matches the running GitHub egpu4 module byte-for-byte. Candidate
compilation and checkpatch (without author sign-off checking) pass; no upstream
submission or DCO sign-off is claimed.

The OPEN/CLOSE mutex is never acquired from AFK callbacks. Those callbacks may
arrive while a firmware command waits for completion. Service-generation checks
prevent an old OPEN completion from publishing availability for its replacement.
The current AFK implementation retains service slots until endpoint shutdown;
this candidate neither changes that lifetime nor fixes eventual slot exhaustion.

This is an audio recovery correction. The separate seven-second delayed physical
HDMI interruption remains under investigation; suppressing a DRM notification
cannot keep scanout alive while firmware has disabled it. Two 60-second display-off cycles with the original module and HDMI audio
endpoint disabled reproduced video-interface teardown about 1.96 seconds after
power-on. AV endpoint initialization is therefore not required to trigger it.

Evidence: `docs/display-followup.md` and the local
`googlebook-resume-compare-20261106/hdmi-service-fix/` test directory.
