/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef APPLE_BOOT_MEDIA_H
#define APPLE_BOOT_MEDIA_H
#include <linux/types.h>

#define APPLE_BOOT_MEDIA_MAX_SOURCES 16
#define APPLE_BOOT_MEDIA_MAX_CANDIDATES 64
#define APPLE_BOOT_MEDIA_UUID_SIZE 37

/* Coverage is supplied by the transport owner, never inferred from a cable.
 * An initialized controller with uncertain DMA ownership is not ABSENT. */
enum apple_boot_source_state {
 APPLE_BOOT_SOURCE_PENDING,
 APPLE_BOOT_SOURCE_COMPLETE,
 APPLE_BOOT_SOURCE_ABSENT,
 APPLE_BOOT_SOURCE_FAILED,
 APPLE_BOOT_SOURCE_UNSAFE,
};
struct apple_boot_source {
 enum apple_boot_source_state state;
 int error;
};
enum apple_boot_transport {
 APPLE_BOOT_TRANSPORT_NVME,
 APPLE_BOOT_TRANSPORT_USB,
};
struct apple_boot_media {
 enum apple_boot_transport transport;
 unsigned int source;
 unsigned int device;
 unsigned int partition;
 u64 route;
 char partuuid[APPLE_BOOT_MEDIA_UUID_SIZE];
 bool efi_system_partition;
 bool has_efi_loader;
};
struct apple_boot_inventory {
 const struct apple_boot_source *sources;
 size_t source_count;
 const struct apple_boot_media *media;
 size_t media_count;
};
/* A non-NULL target is mandatory, even when empty or malformed: never fall
 * back to another installation after a configuration typo. UUIDs are GPT
 * partition UUIDs, not FAT filesystem IDs, device numbers or enclosure IDs.
 * With no target, only a single bootable candidate is selected automatically.
 * Selection performs no I/O and grants no permission to switch controllers.
 */
int apple_boot_partuuid_valid(const char *uuid);
int apple_boot_media_select(const struct apple_boot_inventory *inventory,
                           const char *target_partuuid, size_t *selected);
#endif
