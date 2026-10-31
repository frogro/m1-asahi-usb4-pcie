# NHI DMA implementation gate after Probe10

Status: source audit and implementation plan, not an implemented DMA driver.
No installed bootloader, kernel installer or prototype manifest changes.

## Source baseline and provenance

U-Boot base: b33034a515a068381c4aa28831fb709e91300cd1, followed by
recorded prototype and research patches. Linux reference checkout:
552486f3c101b6b1b54dfa018cea664bbc808e23, with its working-tree files captured
by SHA-256 below. These are attributed open-source driver references;
no Apple driver disassembly or proprietary driver source is used.

## Two distinct IOMMUs

For J274 port1, `t8103.dtsi` describes the NHI DMA IOMMU at 0x501a80000,
compatible `apple,t8103-dart`, SID 1. The tunneled PCIe controller uses the
separate DART at 0x521008000, compatible `apple,t8103-usb4-dart`, 64 streams.
The USB4 variant's TTBR and stream-enable offsets must not be applied to NHI.
The NHI Linux driver requests a 42-bit DMA mask. Validate its aperture and
16-KiB page alignment before allocation; do not use physical addresses as IOVA.

## Required DART work before a hardware DMA test

The current U-Boot T8020 and T8110 flush functions wait forever on BUSY.
Their void callbacks cannot propagate a timeout. Linux's corresponding
stream commands use bounded polling and return an error.

Change the callback to return status and check each probe/map/unmap/remove
call. A failed map must return the established failure value (zero), prevent
later reuse of the uncertain IOVA, and latch the DART fault. A timed-out unmap
must not return its range to the allocator. Generic U-Boot unmap returns void,
so the NHI diagnostic needs an explicit checked fault/teardown path; simply
printing a warning or adding a timeout is insufficient. Stop DMA before unmap.
Never free a buffer that hardware might still access. On uncertain teardown,
retain resources until the existing mandatory full-machine reset.

Also found in the pinned upstream U-Boot source: the T8110 flush writes using
FLUSH_ALL as the register offset (0x100), whereas TLB_CMD is 0x80. Its FLUSH_ALL
constant is BIT(8); Linux encodes FLUSH_ALL as operation zero and FLUSH_SID as
one in bits 10:8. This is outside M1 hardware coverage; isolate its correction
and register-write tests rather than infer M2 results from M1.

Tests should inject permanent BUSY, delayed completion and failed teardown,
assert bounded termination, failure propagation, no IOVA reuse, no buffer
release while ownership is uncertain, and unchanged successful map/unmap.
Then repeat internal-NVMe read regression before enabling NHI DMA.

## NHI transport order

1. Validate and apply the exported RC/NHI/PDF tunables within each resource;
   Probe10 did not apply these NHI tunables or initialize transport.
2. Enable only the intended NHI IOMMU stream, allocate mapped descriptors and
   control buffers, validate address bounds, publish descriptors with explicit
   cache maintenance and ordering suitable for U-Boot.
3. Use Apple's ring layout: TX base 0x10000, RX base 0x80000, stride 0x4000.
   Generic Intel NHI offsets are not interchangeable. Start with control ring 0,
   no PCIe tunnel and bounded polling; leave interrupts disabled deliberately.
4. Match Linux `apple_nhi_ring_configure`: TX ring0 shared-buffer allocation 2,
   RX SOF/EOF masks in both ring options and PDF, flags/E2E programmed together
   when enabling. Preserve descriptor ownership until completion or safe stop.
5. First hardware transaction should read only the host router configuration
   through ring0. Check packet framing/CRC/sequence and timeout paths. Do not
   enable an external PCIe tunnel in that test.
6. Stop rings before firmware sleep and DART teardown. Failed stop means no
   buffer reuse and mandatory reset, not OS handover.
7. Only after repeated host-router reads: program CD321x-derived cable info,
   discover the external router, establish PCIe tunnel, enumerate PCIe/NVMe,
   and perform bounded read-only storage validation before GRUB integration.

Acceptance remains actual hardware evidence. Twelve reported rings and M3
readiness prove neither USB4 link training nor external NVMe boot.
