# Upstream scope after the first external NVMe validation

## Existing foundation

The Ubuntu Asahi 7.2 source used for the test already contains the Apple CIO
reset controller, the ATCPHY USB4 pipehandler mode, device-tree selected DART
DMA apertures, the CD321x/TIPD changes, the Apple ACIO/NHI driver and the
standard Linux USB4/Thunderbolt connection manager. These are the foundation
from Sven Peter's initial Apple USB4/Thunderbolt series. That series supports
XDomain and USB3-via-USB4; it explicitly leaves PCIe and DisplayPort tunnels
for later work.

The prototype in this repository adds the missing external PCIe path. It has
enumerated an Intel TB3 bridge with a Crucial NVMe endpoint and an ASMedia
bridge with a Qualcomm modem endpoint. The normal Linux `nvme` driver handled
the SSD after the host bridge, DART and interrupts had been created.

## Appropriate patch boundary

A final patch must not match an NVMe model or storage class. The upstream
unit is a generic Apple USB4/Thunderbolt PCIe tunnel and host bridge which:

1. derives port, ECAM, DART aperture, stream ID and interrupt resources from
   firmware data and the selected ACIO port;
2. creates and removes the PCI hierarchy as part of the normal USB4 device
   authorization lifecycle;
3. presents every downstream endpoint to the existing Linux PCI drivers;
4. handles orderly removal, authorization rollback and surprise unplug; and
5. uses the existing IOMMU and DMA APIs without endpoint-specific mappings.

NVMe is the first validated client and provides a bounded read/write test.
The ASMedia plus Qualcomm-modem result is the first proof that the design is
not intrinsically storage-specific.

The current loadable modules remain a bring-up and measurement vehicle. They
manually provide resources captured on the M1 Mac mini and therefore are not
yet a generic upstream host implementation.

## Separate feature tracks

- USB3 devices transported through USB4 use the ATCPHY and USB3 tunnel path
  from the existing Apple series.
- DisplayPort output uses a DisplayPort tunnel plus TIPD, DPTX and DCP. PCIe
  enumeration of an SSD does not implement display tunnelling.
- An eGPU is a PCIe client, but it additionally requires large and resizable
  BAR handling, MSI/IOMMU validation, hotplug, power management and a working
  GPU driver. It is a later stress test for the generic PCIe path.
- Thunderbolt networking uses the XDomain/ThunderboltIP path and is separate
  from both PCIe and DisplayPort.

## Next validation targets

1. Boot the dedicated kernel with PCI OF ownership and Apple DART fixes.
2. Repeat the TB3 NVMe lifecycle, direct read and bounded write test.
3. Test the OWC Express 1M2 with a known USB4 cable and record whether it uses
   native USB4 PCIe tunnelling or a USB-storage fallback.
4. Repeat the non-storage ASMedia/Qualcomm endpoint test.
5. Add surprise-unplug and suspend/resume only after deterministic teardown is
   stable.

Primary references:

- Sven Peter, "Initial USB4/Thunderbolt support for Apple M1/M2/M3 SoCs":
  <https://lore.landau.one/lkml/20260906-b4-apple-soc-tbt-v2-0-1f80085f93fb%40kernel.org/T/>
- Linux USB4 and Thunderbolt administration documentation:
  <https://github.com/torvalds/linux/blob/master/Documentation/admin-guide/thunderbolt.rst>
