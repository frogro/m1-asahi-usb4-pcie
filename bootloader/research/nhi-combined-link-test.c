
// SPDX-License-Identifier: GPL-2.0-only
/* Extracted ring diagnostic and production codec; host-only MMIO/DMA mocks.
 * Driver sources attributed to Asahi Linux, Sven Peter, Andreas Noever, Intel.
 */
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <assert.h>
#include <arpa/inet.h>
typedef uint8_t u8;typedef uint32_t u32;typedef uint64_t u64;typedef uint64_t dma_addr_t;typedef unsigned long ulong;
#define BIT(n) (1U<<(n))
#define SZ_16K 16384
#define cpu_to_le32(x) (x)
#define cpu_to_le64(x) (x)
static u32 get_unaligned_be32(const void*p){u32 v;memcpy(&v,p,4);return ntohl(v);}
static void put_unaligned_be32(u32 v,void*p){v=htonl(v);memcpy(p,&v,4);}
struct udevice {int dummy;};
struct iommu_ops {dma_addr_t(*map)(struct udevice*,void*,size_t);};
static u32 nhi[0x100000/4],pdf[0x30004/4],dartregs[0x4000/4];
static void *allocation;static int scenario,freed,mapped,started_dma,flushed,stops;static ulong ticks;static unsigned polls, replies, commands, configured;static u32 host_config[4];
static void *map_sysmem(u64 b,unsigned n){if(b==0x501f00000ULL){assert(n==sizeof(nhi));return nhi;}if(b==0x501db0000ULL){assert(n==sizeof(pdf));return pdf;}assert(b==0x501a80000ULL&&n==sizeof(dartregs));return dartregs;}
static int apple_dart_get_error(struct udevice*d){return scenario==1|| (scenario==6&&mapped)?-ETIMEDOUT:0;}
static void *test_memalign(unsigned a,unsigned n){if(scenario==4)return NULL;assert(a==16384&&n==65536);assert(!posix_memalign(&allocation,a,n));return allocation;}
#define memalign test_memalign
static void test_free(void*p){assert(p==allocation);free(p);allocation=NULL;freed++;}
#define free test_free
static dma_addr_t test_map(struct udevice*d,void*p,size_t n){assert(p==allocation&&n==65536);mapped++;if(scenario==5||scenario==6)return 0;if(scenario==7)return 1;if(scenario==8)return 0xffffc000;return 0x10000;}
static const struct iommu_ops ops={test_map};
static const void*device_get_ops(struct udevice*d){return &ops;}
static void flush_dcache_range(ulong s,ulong e){assert(s>=(ulong)allocation&&e<=(ulong)allocation+65536&&(s%16384)==0&&e>s);flushed=1;}
static void invalidate_dcache_range(ulong s,ulong e){assert(s>=(ulong)allocation&&e<=(ulong)allocation+65536&&(s%16384)==0&&(e-s)==16384);polls++;}
static void mb(void){}
static void udelay(unsigned us){assert(us==50||us==100000);}
static ulong get_timer(ulong base){ticks += scenario==31?250:1; return ticks-base;}
static u32 readl(void*p){return *(u32*)p;}
static void writel(u32 v,void*p);

struct apple_cd321x_status {u32 status,data_status,eudo;u8 usb4_mode;};
static u8 test_drom[48];
static unsigned unlocked, cable_value;
static int ofnode_path(const char*p){return 0;}
static const void *ofnode_get_property(int n,const char*p,int*len){*len=sizeof(test_drom);return test_drom;}
struct udevice;
struct apple_cd321x_status;
struct apple_nhi_host_info { u32 apple, null_ports, port1_cap; };
int apple_nhi_m1_set_cable(const struct apple_cd321x_status *status);
int apple_nhi_m1_link_metadata(const u8 *drom, unsigned int len,
			      u32 status, u32 eudo, u32 *cable);
int apple_nhi_m1_control_check(void);
int apple_nhi_m1_control_read(struct udevice *dart);
typedef int (*apple_nhi_read_fn)(void *context, unsigned int port,
			       unsigned int space, unsigned int offset,
			       unsigned int words, u32 *data);
typedef int (*apple_nhi_host_config_fn)(void *context, u32 *data);
int apple_nhi_m1_inventory(apple_nhi_read_fn read,
			   apple_nhi_host_config_fn configure, void *context,
			   struct apple_nhi_host_info *info);
#define USB4_CFG_FRAME_BYTES 256
#define USB4_CFG_MAX_WORDS 60
#define USB4_CFG_READ 1
#define USB4_CFG_WRITE 2

/* Values are deliberately wider than their wire fields for input validation. */
struct usb4_cfg_request {
	u64 route;
	u32 offset;
	unsigned int port, space, seq, words, type;
};

static u32 usb4_cfg_crc(const u8 *data, size_t size)
{
	u32 crc = ~0U;
	int bit;

	while (size--) {
		crc ^= *data++;
		for (bit = 0; bit < 8; bit++)
			crc = (crc >> 1) ^ ((crc & 1) ? 0x82f63b78 : 0);
	}
	return ~crc;
}

static int usb4_cfg_validate(const struct usb4_cfg_request *req)
{
	if (!req || req->route >> 54 || req->port > 63 || req->space > 3 ||
	    req->seq > 3 || !req->words || req->words > USB4_CFG_MAX_WORDS ||
	    req->offset > 0x1fff || req->words > 0x2000 - req->offset ||
	    (req->type != USB4_CFG_READ && req->type != USB4_CFG_WRITE))
		return -EINVAL;
	return 0;
}

int usb4_cfg_encode(const struct usb4_cfg_request *req, const u32 *data,
		    void *frame, size_t capacity)
{
	u8 *bytes = frame;
	u32 address;
	size_t size;
	unsigned int i;
	int ret = usb4_cfg_validate(req);

	if (ret)
		return ret;
	if (!frame || (req->type == USB4_CFG_WRITE && !data))
		return -EINVAL;
	size = 16 + (req->type == USB4_CFG_WRITE ? 4 * req->words : 0);
	if (capacity < size)
		return -ENOSPC;

	address = req->offset | req->words << 13 | req->port << 19 |
		  req->space << 25 | req->seq << 27;
	put_unaligned_be32(req->route >> 32, bytes);
	put_unaligned_be32(req->route, bytes + 4);
	put_unaligned_be32(address, bytes + 8);
	if (req->type == USB4_CFG_WRITE) {
		for (i = 0; i < req->words; i++)
			put_unaligned_be32(data[i], bytes + 12 + 4 * i);
	}
	put_unaligned_be32(usb4_cfg_crc(bytes, size - 4), bytes + size - 4);
	return size;
}

int usb4_cfg_decode(const struct usb4_cfg_request *req, const void *frame,
		    size_t size, unsigned int sof, unsigned int eof,
		    u32 *data, unsigned int *response_port)
{
	const u8 *bytes = frame;
	u32 hi, address;
	u64 route;
	size_t expected;
	unsigned int i;
	int ret = usb4_cfg_validate(req);

	if (ret)
		return ret;
	if (!frame || !response_port || (req->type == USB4_CFG_READ && !data))
		return -EINVAL;
	if (size < 16 || size > USB4_CFG_FRAME_BYTES || size % 4 || sof)
		return -EPROTO;
	if (get_unaligned_be32(bytes + size - 4) != usb4_cfg_crc(bytes, size - 4))
		return -EBADMSG;
	if (eof != req->type)
		return -EAGAIN;

	hi = get_unaligned_be32(bytes);
	if ((hi & 0xffc00000) != BIT(31))
		return -EPROTO;
	route = (u64)(hi & 0x003fffff) << 32 | get_unaligned_be32(bytes + 4);
	address = get_unaligned_be32(bytes + 8);
	if (route != req->route || ((address >> 27) & 3) != req->seq)
		return -EAGAIN;
	expected = 16 + (req->type == USB4_CFG_READ ? 4 * req->words : 0);
	if (size != expected || address >> 29 || (address & 0x1fff) != req->offset ||
	    ((address >> 13) & 63) != req->words || ((address >> 25) & 3) != req->space)
		return -EPROTO;

	if (req->type == USB4_CFG_READ) {
		for (i = 0; i < req->words; i++)
			data[i] = get_unaligned_be32(bytes + 12 + 4 * i);
	}
	*response_port = (address >> 19) & 63;
	return 0;
}
int apple_nhi_m1_inventory(apple_nhi_read_fn read,
			   apple_nhi_host_config_fn configure, void *context,
			   struct apple_nhi_host_info *info)
{
	u32 data[8], config[4], seen[32], offset, next, cap, vsec, length;
	u32 max_port, upstream, apple = 0, null_ports = 0, port1_cap = 0;
	unsigned int count = 0, i, port;
	int ret;

	if (!read || !configure || !info)
		return -EINVAL;
	ret = read(context, 0, 2, 0, 5, data);
	if (ret)
		return ret;
	max_port = (data[1] >> 14) & 63;
	upstream = (data[1] >> 8) & 63;
	if ((data[0] & 0xffff) != 0x05ac || !max_port || max_port > 16 ||
	    upstream > max_port || data[2] || (data[3] & 0x7fffffff) ||
	    ((data[1] >> 20) & 7))
		return -EPROTO;
	printf("NHI host vendor/device=%08x max-port=%u upstream=%u version=%02x enabled=%u\n",
	       data[0], max_port, upstream, data[4] >> 24, data[3] >> 31);
	/* Linux tb_switch_configure(): root route unchanged, enable CM access,
	 * notification delay 255 ms and CM version appropriate to USB4 version.
	 * Restrict this diagnostic to the observed USB4 v1 host revision.
	 */
	if ((data[4] >> 24) != 0x20 || (data[3] >> 31))
		return -EPROTO;
	config[0] = data[1];
	config[1] = data[2];
	config[2] = data[3] | (1U << 31);
	config[3] = (data[4] & 0xffff0000) | 0x10ff;
	offset = data[1] & 255;
	while (offset) {
		if (offset < 5 || offset > 0x1ffe)
			return -ERANGE;
		if (count == 32)
			return -E2BIG;
		for (i = 0; i < count; i++)
			if (seen[i] == offset)
				return -ELOOP;
		seen[count++] = offset;
		ret = read(context, 0, 2, offset, 2, data);
		if (ret)
			return ret;
		cap = (data[0] >> 8) & 255;
		vsec = (data[0] >> 16) & 255;
		next = data[0] & 255;
		length = 1;
		if (cap == 5) {
			length = data[0] >> 24;
			if (!length) {
				if (next)
					return -EPROTO;
				next = data[1] & 0xffff;
				length = data[1] >> 16;
				if (length < 2)
					return -EPROTO;
			}
			if (length > 0x2000 - offset)
				return -ERANGE;
		} else if (cap != 3) {
			return -EPROTO;
		}
		printf("NHI capability offset=%#x id=%#x vsec=%#x length=%u next=%#x raw=%08x %08x\n",
		       offset, cap, vsec, length, next, data[0], data[1]);
		if (cap == 5 && !vsec) {
			if (apple || length < 2)
				return -EPROTO;
			apple = offset;
		}
		offset = next;
	}
	if (!apple)
		return -ENOENT;
	ret = configure(context, config);
	if (ret)
		return ret;
	ret = read(context, 0, 2, 1, 4, data);
	if (ret)
		return ret;
	for (i = 0; i < 4; i++)
		if (data[i] != config[i])
			return -EIO;
	puts("NHI-HOST-CONFIG PASS; root enabled, no cable-info or tunnel writes\n");
	for (port = 1; port <= max_port; port++) {
		ret = read(context, port, 1, 0, 8, data);
		if (ret)
			return ret;
		printf("NHI adapter port=%u type=%06x header=%08x %08x %08x %08x %08x %08x %08x %08x\n",
		       port, data[2] & 0xffffff, data[0], data[1], data[2],
		       data[3], data[4], data[5], data[6], data[7]);
		if ((data[2] & 0xffffff) && ((data[3] >> 20) & 63) != port)
			return -EPROTO;
		if ((data[2] & 0xffffff) == 1)
			null_ports |= 1U << port;
		if (port == 1)
			port1_cap = data[1] & 255;
	}
	printf("NHI-HOST-INVENTORY PASS capabilities=%u apple=%#x null-ports=%#x; ports read-only\n",
	       count, apple, null_ports);
	info->apple = apple;
	info->null_ports = null_ports;
	info->port1_cap = port1_cap;
	return 0;
}

/* Validate the exported revision-1 DROM without exposing its device UID.
 * The diagnostic is restricted to the measured J274 lane pair 1/2.
 */
int apple_nhi_m1_link_metadata(const u8 *d, unsigned int len,
			      u32 status, u32 eudo, u32 *cable)
{
	u32 crc = ~0U, stored, seen = 0, pair = 0, result = 1;
	unsigned int total, pos, i, bit, n, port;
	u8 uid_crc = 255;

	if (!d || !cable || len < 22 || len > 4096 || d[13] != 1)
		return -EINVAL;
	if (!(status & 1) || !(status & (1U << 23)) || status & (1U << 16) ||
	    ((eudo >> 21) & 7) < 2 || ((eudo >> 21) & 7) > 3)
		return -EPROTONOSUPPORT;
	total = 13 + ((d[14] | d[15] << 8) & 4095);
	if (total < 22 || total > len || len - total > 3)
		return -ERANGE;
	for (i = total; i < len; i++)
		if (d[i]) return -EPROTO;
	for (i = 1; i <= 8; i++) {
		uid_crc ^= d[i];
		for (bit = 0; bit < 8; bit++)
			uid_crc = (uid_crc << 1) ^ ((uid_crc & 128) ? 7 : 0);
	}
	if (uid_crc != d[0]) return -EBADMSG;
	for (i = 13; i < total; i++) {
		crc ^= d[i];
		for (bit = 0; bit < 8; bit++)
			crc = (crc >> 1) ^ ((crc & 1) ? 0x82f63b78 : 0);
	}
	stored = (u32)d[9] | (u32)d[10] << 8 | (u32)d[11] << 16 | (u32)d[12] << 24;
	if (~crc != stored) return -EBADMSG;
	for (pos = 22; pos < total; pos += n) {
		if (total - pos < 2) return -EPROTO;
		n = d[pos];
		if (n < 2 || n > total - pos) return -EPROTO;
		if (!(d[pos + 1] & 128)) continue;
		port = d[pos + 1] & 63;
		if (!port || port > 7 || d[pos + 1] & 64 || seen & (1U << port))
			return -EPROTO;
		seen |= 1U << port;
		if (port <= 2) {
			if (n != 8 || !(d[pos + 2] & 128) ||
			    ((d[pos + 2] >> 4) & 1) != port - 1 ||
			    (d[pos + 3] & 63) != 3 - port) return -EPROTO;
			pair |= 1U << port;
		}
	}
	if (seen != 0xfe || pair != 6) return -EPROTO;
	if (status & 2) result |= 2;
	if ((eudo >> 19) & 3) result |= 4;
	if (((eudo >> 21) & 7) == 3) result |= 16;
	*cable = result;
	return 0;
}
#define NHI_BASE 0x501f00000ULL
#define PDF_BASE 0x501db0000ULL
#define DART_BASE 0x501a80000ULL
#define PAGE SZ_16K
#define RING_COUNT 64
#define DESC_POSTED BIT(22)
#define DESC_DONE BIT(21)
#define DESC_ERROR (BIT(20) | BIT(22))
#define RING_ENABLE BIT(31)
#define RING_RAW BIT(30)
struct diagnostic_desc { u64 address; u32 fields, time; };
struct diagnostic_ring {
 void *buffer, *nhi, *dart_regs;
 struct diagnostic_desc *tx, *rx;
 unsigned int sent, received;
 ulong started;
};

static u32 diagnostic_cable;
static bool diagnostic_cable_valid;

int apple_nhi_m1_set_cable(const struct apple_cd321x_status *status)
{
 const u8 *drom;
 int len, ret;
 diagnostic_cable_valid = false;
 if (!status) return -EINVAL;
 drom = ofnode_get_property(ofnode_path("/soc/cio@501ac0000/nhi@f00000"),
                            "apple,thunderbolt-drom", &len);
 if (!drom || len < 0) return -ENOENT;
 ret = apple_nhi_m1_link_metadata(drom, len, status->data_status,
                                  status->eudo, &diagnostic_cable);
 if (ret) return ret;
 diagnostic_cable_valid = true;
 printf("NHI link metadata PASS: DROM lane pair 1/2 verified, cable=%#x\n", diagnostic_cable);
 return 0;
}

/* No descriptor is recycled. Only one TX is outstanding, up to 63 reads.
 * RX descriptors are published once and only invalidated/read afterwards.
 * This avoids CPU cache writeback racing a device update on a shared line.
 */
static int diagnostic_xfer(void *context, unsigned int port, unsigned int space,
                           unsigned int offset, unsigned int words, u32 *data,
                           unsigned int type, u64 route)
{
 struct diagnostic_ring *r = context;
 struct usb4_cfg_request req = {
  .route = route, .offset = offset, .port = port, .space = space,
  .seq = r->sent & 3, .words = words, .type = type,
 };
 unsigned int slot = r->sent, response_port = 0;
 u32 fields = 0, tx_flags = 0;
 ulong started;
 bool got_reply = false;
 int len, ret = -ETIMEDOUT;

 if (slot >= RING_COUNT - 1 || r->received >= RING_COUNT - 1)
  return -ENOSPC;
 if (get_timer(r->started) >= 10000)
  return -ETIMEDOUT;
 len = usb4_cfg_encode(&req, type == USB4_CFG_WRITE ? data : NULL,
                       r->buffer + 2 * PAGE + slot * 256, 256);
 if (len < 0) return len;
 /* Previous TX completed before this function can be called again. */
 invalidate_dcache_range((ulong)r->tx, (ulong)r->tx + PAGE);
 r->tx[slot].fields = cpu_to_le32(len | (type << 12) | (type << 16) | DESC_POSTED);
 flush_dcache_range((ulong)r->buffer + 2 * PAGE,
                    (ulong)r->buffer + 3 * PAGE);
 flush_dcache_range((ulong)r->tx, (ulong)r->tx + PAGE);
 mb();
 r->sent++;
 writel(r->sent << 16, r->nhi + 0x10008);
 started = get_timer(0);
 while (get_timer(started) < 2000 && get_timer(r->started) < 10000) {
  invalidate_dcache_range((ulong)r->rx, (ulong)r->rx + PAGE);
  invalidate_dcache_range((ulong)r->tx, (ulong)r->tx + PAGE);
  mb();
  tx_flags = readl(&r->tx[slot].fields);
  if (readl(r->dart_regs + 0x40) & BIT(31)) return -EFAULT;
  while (!got_reply && r->received < RING_COUNT - 1) {
   fields = readl(&r->rx[r->received].fields);
   if (!(fields & DESC_DONE)) break;
   if (fields & DESC_ERROR) return -EIO;
   invalidate_dcache_range((ulong)r->buffer + 3 * PAGE,
                           (ulong)r->buffer + 4 * PAGE);
   mb();
   ret = usb4_cfg_decode(&req, r->buffer + 3 * PAGE + r->received * 256,
                        fields & 0xfff, (fields >> 16) & 15,
                        (fields >> 12) & 15, data, &response_port);
   r->received++;
   if (!ret) got_reply = true;
   else if (ret != -EAGAIN) return ret;
  }
  if (got_reply && (tx_flags & DESC_DONE)) {
   printf("NHI xfer type=%u port=%u space=%u offset=%#x words=%u response-port=%u tx=%u rx=%u\n",
          type, port, space, offset, words, response_port, r->sent, r->received);
   return 0;
  }
  udelay(50);
 }
 printf("NHI read timeout port=%u space=%u offset=%#x TX=%#x RX=%#x\n",
        port, space, offset, tx_flags, fields);
 return -ETIMEDOUT;
}

static int diagnostic_read(void *context, unsigned int port, unsigned int space,
                           unsigned int offset, unsigned int words, u32 *data)
{
 return diagnostic_xfer(context, port, space, offset, words, data, USB4_CFG_READ, 0);
}

/* The only write allowed by this probe: four root-router config words.
 * No arbitrary write command, port unlock or cable-information write.
 */
static int diagnostic_host_config(void *context, u32 *data)
{
 if (!data || ((data[0] >> 8) & 63) != 7 ||
     ((data[0] >> 14) & 63) != 7 || ((data[0] >> 20) & 7) ||
     data[1] || data[2] != BIT(31) || data[3] != 0x200010ff)
  return -EINVAL;
 return diagnostic_xfer(context, 0, 2, 1, 4, data, USB4_CFG_WRITE, 0);
}

static int diagnostic_link(struct diagnostic_ring *ring,
                           const struct apple_nhi_host_info *info)
{
 u32 data[5], seen[16], phy = 0, offset = info->port1_cap, value;
 unsigned int count = 0, i, port, state;
 int ret;
 if (!diagnostic_cable_valid || info->null_ports != 6 ||
     info->apple < 5 || info->apple > 0x1ffe) return -EPROTO;
 /* Find the lane PHY capability before changing the link. */
 while (offset) {
  if (offset < 8 || offset > 255 || count == 16) return -ERANGE;
  for (i = 0; i < count; i++) if (seen[i] == offset) return -ELOOP;
  seen[count++] = offset;
  ret = diagnostic_read(ring, 1, 1, offset, 2, data);
  if (ret) return ret;
  if (((data[0] >> 8) & 255) == 1) { phy = offset; break; }
  offset = data[0] & 255;
 }
 if (!phy) return -ENOENT;
 for (port = 1; port <= 2; port++) {
  ret = diagnostic_read(ring, port, 1, 4, 1, &value);
  if (ret) return ret;
  value &= ~BIT(31);
  ret = diagnostic_xfer(ring, port, 1, 4, 1, &value, USB4_CFG_WRITE, 0);
  if (ret) return ret;
  ret = diagnostic_read(ring, port, 1, 4, 1, &value);
  if (ret) return ret;
  if (value & BIT(31)) return -EIO;
 }
 puts("NHI-PORT-UNLOCK PASS lane-pair=1/2\n");
 value = diagnostic_cable;
 ret = diagnostic_xfer(ring, 0, 2, info->apple + 1, 1,
                       &value, USB4_CFG_WRITE, 0);
 if (ret) return ret;
 ret = diagnostic_read(ring, 0, 2, info->apple + 1, 1, &value);
 if (ret) return ret;
 if ((value & 0x1f) != diagnostic_cable) return -EIO;
 printf("NHI-CABLE-INFO PASS value=%#x\n", value);
 for (i = 0; i < 10; i++) {
  ret = diagnostic_read(ring, 1, 1, phy, 2, data);
  if (ret) return ret;
  state = (data[1] >> 26) & 15;
  printf("NHI lane1 state=%u\n", state);
  if (state >= 2 && state <= 6) break;
  udelay(100000);
 }
 if (i == 10) return -ETIMEDOUT;
 ret = diagnostic_xfer(ring, 0, 2, 0, 5, data, USB4_CFG_READ, 1);
 if (ret) return ret;
 if (!data[0] || data[0] == ~0U || !((data[1] >> 14) & 63)) return -EPROTO;
 printf("NHI-REMOTE-READ PASS route=1 header=%08x %08x %08x %08x %08x; no external writes\n",
        data[0], data[1], data[2], data[3], data[4]);
 return 0;
}

int apple_nhi_m1_control_read(struct udevice *dart)
{
 const struct iommu_ops *ops = device_get_ops(dart);
 void *nhi = map_sysmem(NHI_BASE, 0x100000);
 void *pdf = map_sysmem(PDF_BASE, 0x30004);
 void *dart_regs = map_sysmem(DART_BASE, 0x4000);
 struct diagnostic_ring ring = { .nhi = nhi, .dart_regs = dart_regs };
 struct apple_nhi_host_info info;
 void *buffer;
 dma_addr_t dva;
 int i, ret;

 if (!diagnostic_cable_valid) return -EINVAL;
 ret = apple_dart_get_error(dart);
 if (ret) return ret;
 if (readl(dart_regs + 0x40) & BIT(31)) return -EFAULT;
 for (i = 0; i < 12; i++) {
  if (readl(nhi + 0x10010 + i * 0x4000) & RING_ENABLE ||
      readl(nhi + 0x80010 + i * 0x4000) & RING_ENABLE)
   return -EBUSY;
 }
 buffer = memalign(PAGE, 4 * PAGE);
 if (!buffer) return -ENOMEM;
 memset(buffer, 0, 4 * PAGE);
 dva = ops->map(dart, buffer, 4 * PAGE);
 ret = apple_dart_get_error(dart);
 if (ret) return ret; /* uncertain mapping: retain allocation until reset */
 if (!dva) { free(buffer); return -ENOMEM; }
 if (dva < PAGE || (dva & (PAGE - 1)) ||
     dva > 0x100000000ULL - 5 * PAGE) return -ERANGE;
 ring.buffer = buffer;
 ring.tx = buffer;
 ring.rx = buffer + PAGE;
 for (i = 0; i < RING_COUNT - 1; i++) {
  ring.tx[i].address = cpu_to_le64(dva + 2 * PAGE + i * 256);
  ring.rx[i].address = cpu_to_le64(dva + 3 * PAGE + i * 256);
  ring.rx[i].fields = cpu_to_le32(DESC_POSTED);
 }
 flush_dcache_range((ulong)buffer, (ulong)buffer + 4 * PAGE);
 mb();
 writel(0, nhi + 0xd0010);
 writel((u32)dva, nhi + 0x10000);
 writel((u32)(dva >> 32), nhi + 0x10004);
 writel(0, nhi + 0x10008);
 writel(RING_COUNT, nhi + 0x1000c);
 writel(2, nhi + 0x10014);
 writel((u32)(dva + PAGE), nhi + 0x80000);
 writel((u32)((dva + PAGE) >> 32), nhi + 0x80004);
 writel(0, nhi + 0x80008);
 writel((256 << 16) | RING_COUNT, nhi + 0x8000c);
 writel(0xffffffff, nhi + 0x80014);
 writel(0xffffffff, pdf);
 writel(RING_ENABLE | RING_RAW, nhi + 0x80010);
 writel(RING_ENABLE | RING_RAW, nhi + 0x10010);
 writel(RING_COUNT - 1, nhi + 0x80008);
 ring.started = get_timer(0);
 ret = apple_nhi_m1_inventory(diagnostic_read, diagnostic_host_config, &ring, &info);
 if (!ret) ret = diagnostic_link(&ring, &info);
 writel(0, nhi + 0x10010);
 writel(0, nhi + 0x80010);
 mb();
 if (readl(nhi + 0x10010) || readl(nhi + 0x80010)) ret = -EBUSY;
 if (readl(dart_regs + 0x40) & BIT(31)) ret = -EFAULT;
 printf("NHI inventory transport ret=%d sent=%u received=%u DART-error=%#x\n",
        ret, ring.sent, ring.received, readl(dart_regs + 0x40));
 /* A stop readback is not proof that DMA drained. Never free on return. */
 puts("NHI control buffers and DART retained until mandatory reset\n");
 return ret;
}

#undef free
static void response(const u8 *request,unsigned eof,bool badcrc,bool wrongroute){
 assert(replies<63);
 unsigned route=get_unaligned_be32(request+4);
 unsigned address=get_unaligned_be32(request+8),words=(address>>13)&63,offset=address&0x1fff,port=(address>>19)&63,space=(address>>25)&3;
 u32 data[8]={0};assert(words<=8);
 if(eof==3){}
 else if(eof==2){
  assert(route==0);
  if(space==2&&offset==1){assert(words==4);for(unsigned j=0;j<4;j++)host_config[j]=get_unaligned_be32(request+12+j*4);configured++;}
  else if(space==1&&offset==4){assert(port>=1&&port<=2&&words==1);assert(!(get_unaligned_be32(request+12)&BIT(31)));unlocked|=1U<<port;}
  else {assert(space==2&&offset==0x1c&&words==1&&unlocked==6);cable_value=get_unaligned_be32(request+12);assert(cable_value==17);}
 }
 else
 if(route==1){assert(space==2&&offset==0&&words==5&&cable_value==17);data[0]=0x24641b21;data[1]=(4<<14)|(1<<8)|0x1b;data[4]=0x20000000;}
 else if(space==2&&offset==0){
  assert(words==5);data[0]=0x200005ac;data[1]=0x0001c71b;data[4]=0x20000000;
  if(scenario==21)data[1]=(17<<14)|0x1b;
  if(scenario==23)data[2]=1;
 }else if(space==2&&offset==1){assert(words==4&&configured);memcpy(data,host_config,16);if(scenario==34)data[2]=0;
 }else if(space==2&&offset==0x1b){
  assert(words==2);data[0]=0x02000520;
  if(scenario==17)data[0]=0x0200051b;
  if(scenario==18){data[0]=0x00000500;data[1]=(2<<16)|0x2000;}
  if(scenario==19)data[0]=0x02010520;
  if(scenario==20)data[0]=0x01000520;
  if(scenario==24){data[0]=0x00000500;data[1]=(2<<16)|0x20;}
  if(scenario==25){data[0]=0x00000500;data[1]=0;}
  if(scenario==26)data[0]=0x0000ff20;
 }else if(space==2&&offset==0x20){
  assert(words==2);data[0]=0x00000300;
  if(scenario==27)data[0]=0x02000500;
 }else if(space==2&&offset==0x1c){assert(words==1);data[0]=cable_value;}
 else if(space==1&&offset==4){assert(port>=1&&port<=2&&words==1);data[0]=unlocked&(1U<<port)?0:BIT(31);if(scenario==35)data[0]=BIT(31);}
 else if(space==1&&offset==8){assert(port==1&&words==2);data[0]=0x100;data[1]=cable_value?(2U<<26):0;if(scenario==36)data[1]=0;}
 else{
  assert(space==1&&offset==0&&port>=1&&port<=7&&words==8);
  data[0]=0x200005ac;data[1]=8;data[2]=port<=2?1:2;data[3]=port<<20;
  if(scenario==22)data[3]=0;
 }
 u8*b=allocation+3*PAGE+replies*256;struct diagnostic_desc*rx=allocation+PAGE;
 put_unaligned_be32(BIT(31),b);put_unaligned_be32(wrongroute?(route^1):route,b+4);
 put_unaligned_be32((address&~(63<<19))|(7<<19),b+8);
 if(eof!=2)for(unsigned j=0;j<words;j++)put_unaligned_be32(data[j],b+12+j*4);
 unsigned length=16+(eof==2?0:words*4);
 put_unaligned_be32(usb4_cfg_crc(b,length-4)+(badcrc?1:0),b+length-4);
 rx[replies].fields=length|(eof<<12)|DESC_DONE;replies++;
}
static void writel(u32 v,void*p){
 uintptr_t off=(uintptr_t)p-(uintptr_t)nhi;
 if(off<sizeof(nhi)){
  if((off==0x10010||off==0x80010)&&(v&RING_ENABLE))assert(flushed&&mapped&&nhi[0xd0010/4]==0);
  if((off==0x10010||off==0x80010)&&!v){stops++;if(scenario==14)return;}
  *(u32*)p=v;
  if(off==0x10008&&v){
   unsigned slot=(v>>16)-1;assert(slot==commands&&slot<63);commands++;
   started_dma++;
   struct diagnostic_desc*tx=allocation;u8*b=allocation+2*PAGE+slot*256;
   unsigned type=(tx[slot].fields>>12)&15;assert(type==1||type==2);
   assert(tx[slot].fields==((16+(type==2?4*((get_unaligned_be32(b+8)>>13)&63):0))|(type<<12)|(type<<16)|DESC_POSTED));
   assert(tx[slot].address==0x10000+2*PAGE+slot*256);
   assert(get_unaligned_be32(b)==0&&get_unaligned_be32(b+4)<=1);
   if(get_unaligned_be32(b+4))assert(type==1);
   assert(((get_unaligned_be32(b+8)>>27)&3)==(slot&3));
   assert(nhi[0x80008/4]==63&&pdf[0]==0xffffffff&&nhi[0x10014/4]==2);
   assert(nhi[0x1000c/4]==64&&nhi[0x8000c/4]==((256<<16)|64));
   if(scenario==9||(scenario==28&&slot==1)||(scenario==32&&type==2)||(scenario==38&&get_unaligned_be32(b+4)))return;
   if(scenario!=15)tx[slot].fields=DESC_DONE;
   if(scenario==30){while(replies<63)response(b,3,false,false);return;}
   if(scenario==16||scenario==29)response(b,3,false,false);
   response(b,type,scenario==10||(scenario==33&&type==2),scenario==11);
   if(scenario==12)((struct diagnostic_desc*)(allocation+PAGE))[replies-1].fields|=BIT(20);
   if(scenario==13)dartregs[0x40/4]=BIT(31);
  }
  return;
 }
 assert(p==pdf);*(u32*)p=v;
}
static void init_drom(void){
 memset(test_drom,0,sizeof(test_drom));test_drom[13]=1;test_drom[14]=35;
 unsigned pos=22;for(unsigned port=1;port<=7;port++){
  unsigned len=port<=2?8:2;test_drom[pos]=len;test_drom[pos+1]=128|port;
  if(port<=2){test_drom[pos+2]=128|((port-1)<<4);test_drom[pos+3]=3-port;}pos+=len;
 }
 u8 crc=255;for(unsigned i=1;i<=8;i++){crc^=test_drom[i];for(unsigned b=0;b<8;b++)crc=(crc<<1)^((crc&128)?7:0);}test_drom[0]=crc;
 u32 c=usb4_cfg_crc(test_drom+13,35);for(unsigned i=0;i<4;i++)test_drom[9+i]=c>>(8*i);
}
int main(void){struct udevice d;unsigned cases=0;init_drom();
 for(scenario=0;scenario<=38;scenario++){
  free(allocation);allocation=NULL;freed=mapped=started_dma=flushed=stops=0;ticks=polls=replies=commands=configured=unlocked=cable_value=0;memset(host_config,0,sizeof(host_config));
  memset(nhi,0,sizeof(nhi));memset(pdf,0,sizeof(pdf));memset(dartregs,0,sizeof(dartregs));
  if(scenario==2)dartregs[0x40/4]=BIT(31);
  if(scenario==3)nhi[(0x80010+11*0x4000)/4]=RING_ENABLE;
  struct apple_cd321x_status status={.data_status=0x16c00011,.eudo=0x2667e000};
  assert(!apple_nhi_m1_set_cable(&status));
  if(scenario==37)diagnostic_cable_valid=false;
  int ret=apple_nhi_m1_control_read(&d);
  bool pass=scenario==0||scenario==16||scenario==24||scenario==29;
  if(pass?ret!=0:ret>=0){fprintf(stderr,"Unexpected scenario=%d ret=%d\n",scenario,ret);abort();}
  if(pass)assert(commands==23&&replies==(scenario==16||scenario==29?46:23)&&configured==1&&unlocked==6&&cable_value==17);
  if(mapped&&scenario!=5)assert(!freed);
  if(scenario>=1&&scenario<=3)assert(!allocation&&!started_dma);
  if(started_dma){assert(stops==2);if(scenario!=14)assert(!nhi[0x10010/4]&&!nhi[0x80010/4]);}
  assert(ticks<12000);cases++;
 }
 free(allocation);allocation=NULL;
 u32 good[4]={0x0001c71b,0,0x80000000,0x200010ff};
 assert(diagnostic_host_config(NULL,NULL)==-EINVAL);cases++;
 for(unsigned i=0;i<6;i++){
  u32 bad[4];memcpy(bad,good,sizeof(bad));
  if(i==0)bad[0]^=1U<<8;
  if(i==1)bad[0]^=1U<<14;
  if(i==2)bad[0]|=1U<<20;
  if(i==3)bad[1]=1;
  if(i==4)bad[2]=0;
  if(i==5)bad[3]=0;
  assert(diagnostic_host_config(NULL,bad)==-EINVAL);cases++;
 }

 for(unsigned k=0;k<19;k++){
  u8 bad[48];memcpy(bad,test_drom,48);u32 cable=0xdeadbeef,status=0x16c00011,eudo=0x2667e000;unsigned len=48;
  if(k==0)len=21;
  if(k==1)bad[13]=3;
  if(k==2)bad[0]^=1;
  if(k==3)bad[9]^=1;
  if(k==4)bad[14]=60;
  if(k==5)status&=~1U;
  if(k==6)status&=~(1U<<23);
  if(k==7)status|=1U<<16;
  if(k==8)eudo&=~(7U<<21);
  if(k==9)bad[22]=0;
  if(k==10)bad[22]=1;
  if(k==11)bad[22]=49;
  if(k==12)bad[23]|=64;
  if(k==13)bad[23]=(bad[23]&~63)|8;
  if(k==14)bad[25]=1;
  if(k==15)bad[24]&=~128;
  if(k==16)bad[24]|=16;
  if(k==17)bad[31]=(bad[31]&~63)|1;
  if(k==18)bad[47]=(bad[47]&~63)|6;
  if(k>=9){u32 c=usb4_cfg_crc(bad+13,35);for(unsigned j=0;j<4;j++)bad[9+j]=c>>(8*j);}
  assert(apple_nhi_m1_link_metadata(bad,len,status,eudo,&cable)<0);assert(cable==0xdeadbeef);cases++;
 }
 for(unsigned k=0;k<4;k++){
  u32 c=0,status=0x16c00011|(k&1?2:0),eudo=0x2667e000|(k&2?1U<<19:0);
  assert(!apple_nhi_m1_link_metadata(test_drom,48,status,eudo,&c));assert(c==(17U|(k&1?2:0)|(k&2?4:0)));cases++;
 }
 printf("NHI combined-link production/codec mock: %u cases, zero failures; no hardware DMA\n",cases);
}
