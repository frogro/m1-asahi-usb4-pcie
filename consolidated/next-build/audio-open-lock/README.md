# Queued for the next kernel build: release DCP audio lock on DMA failure

Requested by the user on 2026-11-01. This is a kernel error-path correction, kept separate from the experimental U-Boot TB loader. It is not included in the already released egpu3 binaries and is not installed on the Mac.

`dcp_pcm_open()` locks `data_lock` before `dcpaud_init_dma()`. The negative-return branch leaves the mutex locked. A subsequent open then blocks; Probe89 recorded WirePlumber stuck at this mutex after the DMA channel was unavailable. The preceding SIO firmware crash is a separate, unresolved cause of DMA unavailability. This patch preserves error returns and does not conceal the SIO failure or manufacture an audio device.

The candidate adds the missing unlock. Tests extract the complete original/fixed function and exercise failed DMA setup, retry, disconnected-device, later error and successful-open paths: original 13 cases / 8 lock leaks; corrected 13 cases / 0 leaks. An ARM64 `audio.o` build passed against the local 7.2.12 kernel build tree. Full release build and hardware verification remain required.

Before the next build, append this patch to the applicable source replay, update source/patch hash manifests, and use a new kernel release suffix. Do not replace an existing egpu3 artifact with different module contents. Run the whole source/configuration replay and build checks. Both eGPU and non-eGPU profiles share this source defect.
