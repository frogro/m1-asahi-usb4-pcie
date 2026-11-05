/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef APPLE_NHI_M1_H
#define APPLE_NHI_M1_H
#include <linux/types.h>
/* Router/adapter port fields are six bits. Capability-chain and query
 * buffer bounds are independent and must not use this limit. */
#define APPLE_NHI_ROUTER_MAX_PORT 63U
#define APPLE_NHI_INVENTORY_MAX_READS 128U
struct udevice;
struct apple_cd321x_status;
struct apple_nhi_host_info { u32 apple, null_ports, port1_cap, tmu, dp_in_ports; };
/* Optional read-only observer, at most ten link samples. */
void apple_nhi_m1_set_link_sample(void (*callback)(void *), void *context);
/* One-shot preparation after host inventory, before lane/cable writes. */
void apple_nhi_m1_set_pre_link(int (*callback)(void *), void *context);
void apple_nhi_m1_set_queries(bool enabled);
void apple_nhi_m1_set_post_link(void (*callback)(void *), void *context);
/* RAM-only single-use hook, after verified cable info and before link polling. */
void apple_nhi_m1_set_post_cable(int (*callback)(void *), void *context);
int apple_nhi_m1_set_cable(const struct apple_cd321x_status *status);
int apple_nhi_m1_link_metadata(const u8 *drom, unsigned int len,
			      u32 status, u32 eudo, u32 *cable);
int apple_nhi_m1_tbt_metadata(const u8 *drom, unsigned int len,
                            u32 status, u32 device_mode, u32 *cable);
int apple_nhi_m1_control_check(void);
int apple_nhi_m1_control_read(struct udevice *dart);
int apple_nhi_m1_quiesce(void);
/* Called after quiesce and successful ACIO sleep, before Linux handoff. */
int apple_nhi_m1_remove_dart(void);
enum apple_nhi_boot_mode { APPLE_NHI_BOOT_NONE, APPLE_NHI_BOOT_TB3, APPLE_NHI_BOOT_USB4 };
void apple_nhi_m1_set_boot_mode(enum apple_nhi_boot_mode mode);

typedef int (*apple_nhi_read_fn)(void *context, unsigned int port,
			       unsigned int space, unsigned int offset,
			       unsigned int words, u32 *data);
typedef int (*apple_nhi_router_write_fn)(void *, unsigned int, unsigned int, const u32 *);
int apple_nhi_m1_usb4_router_setup(apple_nhi_read_fn, apple_nhi_read_fn,
 apple_nhi_router_write_fn, void (*)(void *), void *, unsigned int);
typedef int (*apple_nhi_host_config_fn)(void *context, u32 *data);
/* Read-only external router inventory; callback is restricted to route 1. */
struct apple_usb4_snapshot {
 u32 port[4], cap[4], old[4][2], nfc[4], control[4];
 u32 hop[4], lane_reserve; /* zero hop means legacy HopID8 */
 bool valid;
};
/* Same four-hop snapshot layout for a USB4 host and a legacy TB3 router. */
int apple_nhi_m1_tb3_preflight(apple_nhi_read_fn, apple_nhi_read_fn, void *, struct apple_usb4_snapshot *);
int apple_nhi_m1_tb3_path_plan(const struct apple_usb4_snapshot *, unsigned int, u32 [4][2]);
int apple_nhi_m1_usb4_preflight(apple_nhi_read_fn, apple_nhi_read_fn, void *, struct apple_usb4_snapshot *);
int apple_nhi_m1_usb4_path_plan(const struct apple_usb4_snapshot *, const u32 *, u32 [4][2]);
int apple_nhi_m1_remote_inventory(apple_nhi_read_fn read, void *context);
int apple_nhi_m1_remote_configure(apple_nhi_read_fn read,
                                apple_nhi_host_config_fn write, void *context,
                                unsigned int upstream);
int apple_nhi_m1_inventory(apple_nhi_read_fn read,
			   apple_nhi_host_config_fn configure, void *context,
			   struct apple_nhi_host_info *info);
typedef int (*apple_nhi_tmu_write_fn)(void *context, unsigned int offset, u32 value);
int apple_nhi_m1_tmu_lowres(apple_nhi_read_fn read,
			  apple_nhi_tmu_write_fn write, void *context, u32 cap);
int apple_nhi_m1_query(apple_nhi_read_fn read, apple_nhi_tmu_write_fn write,
                        void (*wait)(void *), void *context, u32 opcode, u32 metadata);
int apple_nhi_m1_check(void);
int apple_nhi_m1_dart_test(unsigned int stage);
int apple_nhi_m1_tunables_check(void);
int apple_nhi_m1_tunables_apply(bool nhi);
int apple_nhi_m1_usb4_drom_capture(apple_nhi_read_fn, apple_nhi_tmu_write_fn, void (*)(void *), void *, u8 *, unsigned int, unsigned int *);
int apple_nhi_m1_router_lane_capture(apple_nhi_read_fn, void *);
int apple_nhi_m1_usb3_capture(apple_nhi_read_fn read, void *ctx, bool remote);
int apple_nhi_m1_usb3_preflight(apple_nhi_read_fn, apple_nhi_read_fn, void *, struct apple_usb4_snapshot *);
int apple_nhi_m1_usb3_path_plan(const struct apple_usb4_snapshot *, const u32 *, u32 [4][2]);
int apple_nhi_m1_auto_preflight(apple_nhi_read_fn, apple_nhi_read_fn, void *, struct apple_usb4_snapshot *, struct apple_usb4_snapshot *, unsigned int *);
struct apple_nhi_child { u64 route; u32 lane, pcie_down; };
int apple_nhi_m1_child_discover(apple_nhi_read_fn, void *, const u8 *, unsigned int,
                              struct apple_nhi_child *);
int apple_nhi_m1_remote_configure_route(apple_nhi_read_fn,
 apple_nhi_host_config_fn, void *, unsigned int, u64, unsigned int);
int apple_nhi_m1_child_path_plan(const struct apple_usb4_snapshot *,unsigned int,u32 [4][2]);
int apple_nhi_m1_child_preflight(apple_nhi_read_fn,apple_nhi_read_fn,void *,
 const struct apple_nhi_child *,unsigned int,unsigned int,struct apple_usb4_snapshot *);
#endif
