
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
static void *allocation;static int scenario,freed,mapped,started_dma,flushed,stops;static ulong ticks;static unsigned polls;
static void *map_sysmem(u64 b,unsigned n){if(b==0x501f00000ULL){assert(n==sizeof(nhi));return nhi;}if(b==0x501db0000ULL){assert(n==sizeof(pdf));return pdf;}assert(b==0x501a80000ULL&&n==sizeof(dartregs));return dartregs;}
static int apple_dart_get_error(struct udevice*d){return scenario==1|| (scenario==6&&mapped)?-ETIMEDOUT:0;}
static void *test_memalign(unsigned a,unsigned n){if(scenario==4)return NULL;assert(a==16384&&n==65536);assert(!posix_memalign(&allocation,a,n));return allocation;}
#define memalign test_memalign
static void test_free(void*p){assert(p==allocation);free(p);allocation=NULL;freed++;}
#define free test_free
static dma_addr_t test_map(struct udevice*d,void*p,size_t n){assert(p==allocation&&n==65536);mapped++;if(scenario==5||scenario==6)return 0;if(scenario==7)return 1;if(scenario==8)return 0xffffc000;return 0x10000;}
static const struct iommu_ops ops={test_map};
static const void*device_get_ops(struct udevice*d){return &ops;}
static void flush_dcache_range(ulong s,ulong e){assert(s==(ulong)allocation&&e==s+65536);flushed=1;}
static void invalidate_dcache_range(ulong s,ulong e){assert(s>=(ulong)allocation&&e<=(ulong)allocation+65536&&(s%16384)==0&&(e-s)==16384);polls++;}
static void mb(void){}
static void udelay(unsigned us){assert(us==50);}
static ulong get_timer(ulong base){return ++ticks-base;}
static u32 readl(void*p){return *(u32*)p;}
static void writel(u32 v,void*p);
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
#define NHI_BASE 0x501f00000ULL
#define PDF_BASE 0x501db0000ULL
#define DART_BASE 0x501a80000ULL
#define PAGE SZ_16K
#define RING_COUNT 16
#define DESC_POSTED BIT(22)
#define DESC_DONE BIT(21)
#define DESC_ERROR (BIT(20) | BIT(22))
#define RING_ENABLE BIT(31)
#define RING_RAW BIT(30)
struct diagnostic_desc { u64 address; u32 fields, time; };

int apple_nhi_m1_control_read(struct udevice *dart)
{
 const struct iommu_ops *ops = device_get_ops(dart);
 const struct usb4_cfg_request req = {
  .route = 0, .offset = 0, .port = 0, .space = 2, .seq = 0,
  .words = 4, .type = USB4_CFG_READ,
 };
 void *nhi = map_sysmem(NHI_BASE, 0x100000);
 void *pdf = map_sysmem(PDF_BASE, 0x30004);
 void *dart_regs = map_sysmem(DART_BASE, 0x4000);
 struct diagnostic_desc *tx, *rx;
 void *buffer;
 dma_addr_t dva;
 ulong started;
 u32 fields = 0, data[4], tx_flags = 0;
 unsigned int port = 0, next = 0;
 int len, i, ret;
 bool got_reply = false, enabled = false;

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
 len = usb4_cfg_encode(&req, NULL, buffer + 2 * PAGE, 256);
 if (len < 0) { free(buffer); return len; }
 dva = ops->map(dart, buffer, 4 * PAGE);
 ret = apple_dart_get_error(dart);
 if (ret) return ret; /* uncertain mapping: retain allocation until reset */
 if (!dva) { free(buffer); return -ENOMEM; }
 if (dva < PAGE || (dva & (PAGE - 1)) ||
     dva > 0x100000000ULL - 5 * PAGE) return -ERANGE;
 tx = buffer;
 rx = buffer + PAGE;
 tx[0].address = cpu_to_le64(dva + 2 * PAGE);
 tx[0].fields = cpu_to_le32(len | BIT(12) | BIT(16) | DESC_POSTED);
 for (i = 0; i < RING_COUNT - 1; i++) {
  rx[i].address = cpu_to_le64(dva + 3 * PAGE + i * 256);
  rx[i].fields = cpu_to_le32(DESC_POSTED);
 }
 flush_dcache_range((ulong)buffer, (ulong)buffer + 4 * PAGE);
 mb();
 /* Polling only. RX accepts all PDFs, as Linux control rings do. */
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
 enabled = true;
 writel(RING_COUNT - 1, nhi + 0x80008);
 writel(1 << 16, nhi + 0x10008);
 ret = -ETIMEDOUT;
 started = get_timer(0);
 while (get_timer(started) < 2000) {
  invalidate_dcache_range((ulong)rx, (ulong)rx + PAGE);
  invalidate_dcache_range((ulong)tx, (ulong)tx + PAGE);
  mb();
  tx_flags = readl(&tx[0].fields);
  if (readl(dart_regs + 0x40) & BIT(31)) { ret = -EFAULT; break; }
  while (!got_reply && next < RING_COUNT - 1) {
   fields = readl(&rx[next].fields);
   if (!(fields & DESC_DONE)) break;
   if (fields & DESC_ERROR) { ret = -EIO; goto stop; }
   invalidate_dcache_range((ulong)buffer + 3 * PAGE,
                          (ulong)buffer + 4 * PAGE);
   mb();
   ret = usb4_cfg_decode(&req, buffer + 3 * PAGE + next * 256,
                        fields & 0xfff, (fields >> 16) & 15,
                        (fields >> 12) & 15, data, &port);
   next++;
   if (!ret) got_reply = true;
   else if (ret != -EAGAIN) goto stop;
  }
  if (got_reply && (tx_flags & DESC_DONE)) { ret = 0; break; }
  ret = -ETIMEDOUT;
  udelay(50);
 }
stop:
 if (enabled) {
  writel(0, nhi + 0x10010);
  writel(0, nhi + 0x80010);
  mb();
  if (readl(nhi + 0x10010) || readl(nhi + 0x80010)) ret = -EBUSY;
 }
 printf("NHI control ret=%d TX=%#x RX=%#x consumed=%u DART-error=%#x\n",
        ret, tx_flags, fields, next, readl(dart_regs + 0x40));
 /* Even successful stop readback is not proof that DMA has drained.
  * Keep both mapping and allocation, including page tables, until reset.
  */
 puts("NHI control buffers and DART retained until mandatory reset\n");
 if (!ret) {
  printf("NHI-HOST-READ PASS port=%u data=%08x %08x %08x %08x\n",
         port, data[0], data[1], data[2], data[3]);
 }
 return ret;
}
#undef free
static void reply(unsigned index,unsigned eof,bool badcrc,bool wrongroute){
 u8*b=allocation+3*PAGE+index*256;struct diagnostic_desc*rx=allocation+PAGE;
 put_unaligned_be32(BIT(31),b);put_unaligned_be32(wrongroute?1:0,b+4);put_unaligned_be32((4<<13)|(2<<25),b+8);
 for(unsigned j=0;j<4;j++)put_unaligned_be32(0x12340000+j,b+12+j*4);
 put_unaligned_be32(usb4_cfg_crc(b,28)+(badcrc?1:0),b+28);
 rx[index].fields=32|(eof<<12)|DESC_DONE;
}
static void writel(u32 v,void*p){
 uintptr_t off=(uintptr_t)p-(uintptr_t)nhi;
 if(off<sizeof(nhi)){
  if((off==0x10010||off==0x80010)&&(v&RING_ENABLE))assert(flushed&&mapped&&nhi[0xd0010/4]==0);
  if((off==0x10010||off==0x80010)&&!v){stops++;if(scenario==14)return;}
  *(u32*)p=v;
  if(off==0x10008&&v==(1<<16)){
   started_dma++;
   struct diagnostic_desc*tx=allocation;u8*b=allocation+2*PAGE;
   assert(tx[0].fields==(16|BIT(12)|BIT(16)|DESC_POSTED));
   assert(get_unaligned_be32(b)==0&&get_unaligned_be32(b+4)==0&&get_unaligned_be32(b+8)==((4<<13)|(2<<25)));
   assert(nhi[0x80008/4]==15&&pdf[0]==0xffffffff&&nhi[0x10014/4]==2);
   if(scenario==9)return;
   if(scenario!=15)tx[0].fields=DESC_DONE;
   reply(0,scenario==16?3:1,scenario==10,scenario==11);
   if(scenario==12)((struct diagnostic_desc*)(allocation+PAGE))[0].fields|=BIT(20);
   if(scenario==13)dartregs[0x40/4]=BIT(31);
   if(scenario==16)reply(1,1,false,false);
  }
  return;
 }
 assert(p==pdf);*(u32*)p=v;
}
int main(void){struct udevice d;unsigned cases=0;
 for(scenario=0;scenario<=16;scenario++){
  free(allocation);allocation=NULL;freed=mapped=started_dma=flushed=stops=0;ticks=polls=0;
  memset(nhi,0,sizeof(nhi));memset(pdf,0,sizeof(pdf));memset(dartregs,0,sizeof(dartregs));
  if(scenario==2)dartregs[0x40/4]=BIT(31);
  if(scenario==3)nhi[(0x80010+11*0x4000)/4]=RING_ENABLE;
  int ret=apple_nhi_m1_control_read(&d);
  assert((scenario==0||scenario==16)?ret==0:ret<0);
  if(mapped&&scenario!=5)assert(!freed);
  if(scenario>=1&&scenario<=3)assert(!allocation&&!started_dma);
  if(started_dma){assert(stops==2);if(scenario!=14)assert(!nhi[0x10010/4]&&!nhi[0x80010/4]);}
  assert(ticks<2100);cases++;
 }
 free(allocation);allocation=NULL;
 printf("NHI control ring production/codec mock: %u cases, zero failures; no hardware DMA\n",cases);
}
