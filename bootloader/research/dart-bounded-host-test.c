
// SPDX-License-Identifier: GPL-2.0+
/* Extracted Apple DART implementation: Copyright 2021 Mark Kettenis.
 * Host mocks exercise fault propagation and resource ownership, not DMA.
 * Poll macro from U-Boot linux/iopoll.h, GPL-2.0, Copyright 2012-2014
 * The Linux Foundation. All rights reserved.
 */
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <assert.h>
#include <malloc.h>
typedef uint64_t u64;
typedef uint32_t u32;
typedef uint64_t dma_addr_t;
typedef uint64_t phys_addr_t;
typedef uint64_t phys_size_t;
#define BIT(n) (1U<<(n))
#define GENMASK(h,l) ((~0U>>(31-(h))) & (~0U<<(l)))
#define DIV_ROUND_UP(x,y) (((x)+(y)-1)/(y))
#define min(x,y) ((x)<(y)?(x):(y))
#define ALIGN_DOWN(x,a) ((x)&~((typeof(x))(a)-1))
#define ALIGN(x,a) ALIGN_DOWN((x)+(a)-1,a)
#define SZ_16K 16384ULL
#define SZ_4G (1ULL<<32)
#define time_after(a,b) ((long)((b)-(a))<0)
struct lmb {bool reserved; unsigned setups,teardowns,allocs,frees;};
struct udevice;
struct iommu_ops {dma_addr_t(*map)(struct udevice*,void*,size_t);void(*unmap)(struct udevice*,dma_addr_t,size_t);};
struct udevice {void*priv; const void*ops;const char*compat;};
static unsigned char regs[0x8000];
static unsigned flushes,fail_flush,delay_reads,reads,mmio_writes,clock_us;
static unsigned last_cmd_offset,last_cmd_value;
static bool force_translation;
static bool dev_read_bool(struct udevice*d,const char*p){return force_translation;}
static unsigned long timer_get_us(void){return clock_us;}
static void udelay(unsigned us){clock_us+=us;}
static void mb(void){}
static void flush_dcache_range(unsigned long a,unsigned long b){}
static u32 readl(const void*p){
 unsigned off=(const unsigned char*)p-regs;
 if(off==0x20||off==0x80){reads++;if((fail_flush&&flushes>=fail_flush)||reads<=delay_reads)return off==0x20?BIT(2):BIT(31);return 0;}
 u32 v;memcpy(&v,p,4);return v;
}
static void writel(u32 v,void*p){
 unsigned off=(unsigned char*)p-regs;assert(off+4<=sizeof(regs));mmio_writes++;memcpy(p,&v,4);
 if(off==0x20||off==0x80){flushes++;reads=0;last_cmd_offset=off;last_cmd_value=v;}
}
static void *dev_get_priv(struct udevice*d){return d->priv;}
static const void*device_get_ops(struct udevice*d){return d->ops;}
static void*dev_read_addr_ptr(struct udevice*d){return regs;}
static bool device_is_compatible(struct udevice*d,const char*s){return !strcmp(d->compat,s);}
static int io_lmb_setup(struct lmb*l){l->setups++;return 0;}
static int io_lmb_add(struct lmb*l,phys_addr_t a,phys_size_t s){return 0;}
static void io_lmb_teardown(struct lmb*l){l->teardowns++;}
static phys_addr_t io_lmb_alloc(struct lmb*l,phys_size_t n,phys_size_t a){if(l->reserved)return 0;l->reserved=true;l->allocs++;return 16384;}
static void io_lmb_free(struct lmb*l,phys_addr_t a,phys_size_t n){assert(l->reserved);l->reserved=false;l->frees++;}
#define read_poll_timeout(op, val, cond, sleep_us, timeout_us, args...)	\
({ \
	unsigned long timeout = timer_get_us() + timeout_us; \
	for (;;) { \
		(val) = op(args); \
		if (cond) \
			break; \
		if (timeout_us && time_after(timer_get_us(), timeout)) { \
			(val) = op(args); \
			break; \
		} \
		if (sleep_us) \
			udelay(sleep_us); \
	} \
	(cond) ? 0 : -ETIMEDOUT; \
})

#define readx_poll_sleep_timeout(op, addr, val, cond, sleep_us, timeout_us) \
	read_poll_timeout(op, val, cond, sleep_us, timeout_us, addr)

#define readb_poll_sleep_timeout(addr, val, cond, sleep_us, timeout_us) \
	readx_poll_sleep_timeout(readb, addr, val, cond, sleep_us, timeout_us)

#define readl_poll_sleep_timeout(addr, val, cond, sleep_us, timeout_us) \
	readx_poll_sleep_timeout(readl, addr, val, cond, sleep_us, timeout_us)

#define readx_poll_timeout(op, addr, val, cond, timeout_us) \
	read_poll_timeout(op, val, cond, false, timeout_us, addr)

#define readb_poll_timeout(addr, val, cond, timeout_us) \
	readx_poll_timeout(readb, addr, val, cond, timeout_us)

#define DART_PARAMS2		0x0004
#define  DART_PARAMS2_BYPASS_SUPPORT	BIT(0)

#define DART_T8020_TLB_CMD		0x0020
#define  DART_T8020_TLB_CMD_FLUSH		BIT(20)
#define  DART_T8020_TLB_CMD_BUSY		BIT(2)
#define DART_T8020_TLB_SIDMASK		0x0034
#define DART_T8020_ERROR		0x0040
#define DART_T8020_ERROR_ADDR_LO	0x0050
#define DART_T8020_ERROR_ADDR_HI	0x0054
#define DART_T8020_CONFIG		0x0060
#define  DART_T8020_CONFIG_LOCK			BIT(15)
#define DART_T8020_SID_ENABLE		0x00fc
#define DART_T8103_USB4_SID_ENABLE	0x00f8
#define DART_T8020_TCR_BASE		0x0100
#define  DART_T8020_TCR_TRANSLATE_ENABLE	BIT(7)
#define  DART_T8020_TCR_BYPASS_DART		BIT(8)
#define  DART_T8020_TCR_BYPASS_DAPF		BIT(12)
#define DART_T8020_TTBR_BASE		0x0200
#define DART_T8020_USB4_TTBR_BASE	0x0400
#define  DART_T8020_TTBR_VALID			BIT(31)

#define DART_T8110_PARAMS4		0x000c
#define  DART_T8110_PARAMS4_NSID_MASK		(0x1ff << 0)
#define DART_T8110_TLB_CMD		0x0080
#define  DART_T8110_TLB_CMD_BUSY		BIT(31)
#define  DART_T8110_TLB_CMD_FLUSH_ALL		0
#define DART_T8110_ERROR		0x0100
#define DART_T8110_ERROR_MASK		0x0104
#define DART_T8110_ERROR_ADDR_LO	0x0170
#define DART_T8110_ERROR_ADDR_HI	0x0174
#define DART_T8110_PROTECT		0x0200
#define  DART_T8110_PROTECT_TTBR_TCR		BIT(0)
#define DART_T8110_SID_ENABLE_BASE	0x0c00
#define DART_T8110_TCR_BASE		0x1000
#define  DART_T8110_TCR_BYPASS_DAPF		BIT(2)
#define  DART_T8110_TCR_BYPASS_DART		BIT(1)
#define  DART_T8110_TCR_TRANSLATE_ENABLE	BIT(0)
#define DART_T8110_TTBR_BASE		0x1400
#define  DART_T8110_TTBR_VALID			BIT(0)

#define DART_SID_ENABLE(priv, idx) \
	((priv)->sid_enable_base + 4 * (idx))
#define DART_TCR(priv, sid)	((priv)->tcr_base + 4 * (sid))
#define DART_TTBR(priv, sid, idx)	\
	((priv)->ttbr_base + 4 * (priv)->nttbr * (sid) + 4 * (idx))
#define  DART_TTBR_SHIFT	12

/* Linux uses 100 us; keep a bounded 1 ms diagnostic margin here. */
#define DART_TLB_TIMEOUT_US	1000

#define DART_PAGE_SIZE		SZ_16K
#define DART_PAGE_MASK		(DART_PAGE_SIZE - 1)

#define DART_L1_TABLE		0x3
#define DART_L2_INVAL		0
#define DART_L2_VALID		BIT(0)
#define DART_L2_FULL_PAGE	BIT(1)
#define DART_L2_START(addr)	((((addr) & DART_PAGE_MASK) >> 2) << 52)
#define DART_L2_END(addr)	((((addr) & DART_PAGE_MASK) >> 2) << 40)

struct apple_dart_priv {
	void *base;
	u64 *l1, *l2;
	int bypass, shift;

	struct lmb io_lmb;

	dma_addr_t dvabase;
	dma_addr_t dvaend;

	int nsid;
	int nttbr;
	int sid_enable_base;
	int tcr_base;
	u32 tcr_translate_enable;
	u32 tcr_bypass;
	int ttbr_base;
	u32 ttbr_valid;
	int (*flush_tlb)(struct apple_dart_priv *priv);
	int error;
};

static int apple_dart_t8020_flush_tlb(struct apple_dart_priv *priv)
{
	int i;
	u32 val;

	/* Publish page-table writes before invalidating cached translations. */
	mb();
	for (i = 0; i < DIV_ROUND_UP(priv->nsid, 32); i++) {
		int bits = min(priv->nsid - 32 * i, 32);

		writel(GENMASK(bits - 1, 0),
		       priv->base + DART_T8020_TLB_SIDMASK + 4 * i);
	}
	writel(DART_T8020_TLB_CMD_FLUSH, priv->base + DART_T8020_TLB_CMD);
	return readl_poll_sleep_timeout(priv->base + DART_T8020_TLB_CMD,
					val, !(val & DART_T8020_TLB_CMD_BUSY),
					1, DART_TLB_TIMEOUT_US);
}

static int apple_dart_t8110_flush_tlb(struct apple_dart_priv *priv)
{
	u32 val;

	/* Publish page-table writes before invalidating cached translations. */
	mb();

	writel(DART_T8110_TLB_CMD_FLUSH_ALL,
	       priv->base + DART_T8110_TLB_CMD);
	return readl_poll_sleep_timeout(priv->base + DART_T8110_TLB_CMD,
					val, !(val & DART_T8110_TLB_CMD_BUSY),
					1, DART_TLB_TIMEOUT_US);
}

/* A failed invalidation leaves translation ownership uncertain. */
static int apple_dart_sync(struct apple_dart_priv *priv)
{
	if (!priv->error) {
		priv->error = priv->flush_tlb(priv);
		if (priv->error)
			printf("Apple DART: TLB invalidation failed (%d); DMA mappings blocked\n",
			       priv->error);
	}
	return priv->error;
}

static dma_addr_t apple_dart_map(struct udevice *dev, void *addr, size_t size)
{
	struct apple_dart_priv *priv = dev_get_priv(dev);
	phys_addr_t paddr, dva;
	phys_size_t psize, off;
	int i, idx;

	/* Zero is outside our IOVA aperture and denotes a failed mapping. */
	if (priv->error || !size || size - 1 > (phys_addr_t)-1 - (phys_addr_t)addr)
		return 0;
	if (priv->bypass)
		return (phys_addr_t)addr;

	paddr = ALIGN_DOWN((phys_addr_t)addr, DART_PAGE_SIZE);
	off = (phys_addr_t)addr - paddr;
	/* Bound before adding or rounding, including alignment overflow. */
	if (size > priv->dvaend - priv->dvabase - off)
		return 0;
	psize = ALIGN(size + off, DART_PAGE_SIZE);

	dva = io_lmb_alloc(&priv->io_lmb, psize, DART_PAGE_SIZE);
	if (!dva)
		return 0;

	idx = dva / DART_PAGE_SIZE;
	for (i = 0; i < psize / DART_PAGE_SIZE; i++) {
		priv->l2[idx + i] = (paddr  >> priv->shift) | DART_L2_VALID |
			DART_L2_START(0LL) | DART_L2_END(~0LL);
		paddr += DART_PAGE_SIZE;
	}
	flush_dcache_range((unsigned long)&priv->l2[idx],
			   (unsigned long)&priv->l2[idx + i]);
	/* Keep the IOVA reserved on failure; never publish it to the device. */
	if (apple_dart_sync(priv))
		return 0;

	return dva + off;
}

static void apple_dart_unmap(struct udevice *dev, dma_addr_t addr, size_t size)
{
	struct apple_dart_priv *priv = dev_get_priv(dev);
	phys_addr_t dva;
	phys_size_t psize;
	int i, idx;

	if (priv->error || priv->bypass)
		return;
	/* Reject failed mappings and ranges outside the page-table aperture. */
	if (!size || addr < priv->dvabase || addr >= priv->dvaend ||
	    size > priv->dvaend - addr)
		return;

	dva = ALIGN_DOWN(addr, DART_PAGE_SIZE);
	psize = size + (addr - dva);
	psize = ALIGN(psize, DART_PAGE_SIZE);

	idx = dva / DART_PAGE_SIZE;
	for (i = 0; i < psize / DART_PAGE_SIZE; i++)
		priv->l2[idx + i] = DART_L2_INVAL;
	flush_dcache_range((unsigned long)&priv->l2[idx],
			   (unsigned long)&priv->l2[idx + i]);
	/* Do not recycle an IOVA whose old translation may still be cached. */
	if (apple_dart_sync(priv))
		return;

	io_lmb_free(&priv->io_lmb, dva, psize);
}

static struct iommu_ops apple_dart_ops = {
	.map = apple_dart_map,
	.unmap = apple_dart_unmap,
};

int apple_dart_get_error(struct udevice *dev)
{
	struct apple_dart_priv *priv;

	if (!dev || device_get_ops(dev) != &apple_dart_ops)
		return -EINVAL;
	priv = dev_get_priv(dev);
	return priv->error;
}

/* Diagnostic only: caller must prove all DMA engines idle first. */
int apple_dart_limit_stream(struct udevice *dev, unsigned int stream)
{
	struct apple_dart_priv *priv;
	int sid, i, ret = apple_dart_get_error(dev);

	if (ret)
		return ret;
	priv = dev_get_priv(dev);
	if (priv->bypass || !priv->l1 || stream >= priv->nsid)
		return -EINVAL;
	for (sid = 0; sid < priv->nsid; sid++)
		writel(0, priv->base + DART_TCR(priv, sid));
	ret = apple_dart_sync(priv);
	if (ret)
		return ret;
	for (i = 0; i < DIV_ROUND_UP(priv->nsid, 32); i++)
		writel(i == stream / 32 ? BIT(stream % 32) : 0,
		       priv->base + DART_SID_ENABLE(priv, i));
	writel(priv->tcr_translate_enable,
	       priv->base + DART_TCR(priv, stream));
	return 0;
}

static int apple_dart_probe(struct udevice *dev)
{
	struct apple_dart_priv *priv = dev_get_priv(dev);
	dma_addr_t addr;
	phys_addr_t l2;
	int ntte, nl1, nl2;
	int ret, sid, i;
	u32 params2, params4;

	priv->base = dev_read_addr_ptr(dev);
	if (!priv->base)
		return -EINVAL;

	if (device_is_compatible(dev, "apple,t8110-dart")) {
		params4 = readl(priv->base + DART_T8110_PARAMS4);
		priv->nsid = params4 & DART_T8110_PARAMS4_NSID_MASK;
		priv->nttbr = 1;
		priv->sid_enable_base = DART_T8110_SID_ENABLE_BASE;
		priv->tcr_base = DART_T8110_TCR_BASE;
		priv->tcr_translate_enable = DART_T8110_TCR_TRANSLATE_ENABLE;
		priv->tcr_bypass =
		    DART_T8110_TCR_BYPASS_DAPF | DART_T8110_TCR_BYPASS_DART;
		priv->ttbr_base = DART_T8110_TTBR_BASE;
		priv->ttbr_valid = DART_T8110_TTBR_VALID;
		priv->flush_tlb = apple_dart_t8110_flush_tlb;
	} else {
		priv->nsid = 16;
		priv->nttbr = 4;
		priv->sid_enable_base = DART_T8020_SID_ENABLE;
		priv->tcr_base = DART_T8020_TCR_BASE;
		priv->tcr_translate_enable = DART_T8020_TCR_TRANSLATE_ENABLE;
		priv->tcr_bypass =
		    DART_T8020_TCR_BYPASS_DAPF | DART_T8020_TCR_BYPASS_DART;
		priv->ttbr_base = DART_T8020_TTBR_BASE;
		priv->ttbr_valid = DART_T8020_TTBR_VALID;
		priv->flush_tlb = apple_dart_t8020_flush_tlb;
	}
	if (device_is_compatible(dev, "apple,t8103-usb4-dart")) {
		priv->nsid = 64;
		priv->sid_enable_base = DART_T8103_USB4_SID_ENABLE;
		priv->ttbr_base = DART_T8020_USB4_TTBR_BASE;
		priv->tcr_bypass = 0;
	}

	if (device_is_compatible(dev, "apple,t6000-dart") ||
	    device_is_compatible(dev, "apple,t8110-dart"))
		priv->shift = 4;

	priv->dvabase = DART_PAGE_SIZE;
	priv->dvaend = SZ_4G - DART_PAGE_SIZE;

	ret = io_lmb_setup(&priv->io_lmb);
	if (ret)
		return ret;
	ret = io_lmb_add(&priv->io_lmb, priv->dvabase,
			 priv->dvaend - priv->dvabase);
	if (ret) {
		io_lmb_teardown(&priv->io_lmb);
		return ret;
	}

	/* Disable translations. */
	for (sid = 0; sid < priv->nsid; sid++)
		writel(0, priv->base + DART_TCR(priv, sid));

	/* Remove page tables. */
	for (sid = 0; sid < priv->nsid; sid++) {
		for (i = 0; i < priv->nttbr; i++)
			writel(0, priv->base + DART_TTBR(priv, sid, i));
	}
	ret = apple_dart_sync(priv);
	if (ret) {
		io_lmb_teardown(&priv->io_lmb);
		return ret;
	}

	params2 = readl(priv->base + DART_PARAMS2);
	if (priv->tcr_bypass && (params2 & DART_PARAMS2_BYPASS_SUPPORT) &&
	    !dev_read_bool(dev, "u-boot,force-dart-translation")) {
		for (sid = 0; sid < priv->nsid; sid++) {
			writel(priv->tcr_bypass,
			       priv->base + DART_TCR(priv, sid));
		}
		priv->bypass = 1;
		return 0;
	}

	ntte = DIV_ROUND_UP(priv->dvaend, DART_PAGE_SIZE);
	nl2 = DIV_ROUND_UP(ntte, DART_PAGE_SIZE / sizeof(u64));
	nl1 = DIV_ROUND_UP(nl2, DART_PAGE_SIZE / sizeof(u64));

	priv->l2 = memalign(DART_PAGE_SIZE, nl2 * DART_PAGE_SIZE);
	if (!priv->l2) {
		io_lmb_teardown(&priv->io_lmb);
		return -ENOMEM;
	}
	memset(priv->l2, 0, nl2 * DART_PAGE_SIZE);
	flush_dcache_range((unsigned long)priv->l2,
			   (unsigned long)priv->l2 + nl2 * DART_PAGE_SIZE);

	priv->l1 = memalign(DART_PAGE_SIZE, nl1 * DART_PAGE_SIZE);
	if (!priv->l1) {
		free(priv->l2);
		priv->l2 = NULL;
		io_lmb_teardown(&priv->io_lmb);
		return -ENOMEM;
	}
	memset(priv->l1, 0, nl1 * DART_PAGE_SIZE);
	l2 = (phys_addr_t)priv->l2;
	for (i = 0; i < nl2; i++) {
		priv->l1[i] = (l2 >> priv->shift) | DART_L1_TABLE;
		l2 += DART_PAGE_SIZE;
	}
	flush_dcache_range((unsigned long)priv->l1,
			   (unsigned long)priv->l1 + nl1 * DART_PAGE_SIZE);

	/* Install page tables. */
	for (sid = 0; sid < priv->nsid; sid++) {
		addr = (phys_addr_t)priv->l1;
		for (i = 0; i < nl1; i++) {
			writel(addr >> DART_TTBR_SHIFT | priv->ttbr_valid,
			       priv->base + DART_TTBR(priv, sid, i));
			addr += DART_PAGE_SIZE;
		}
	}
	/* Tables are now hardware-visible: retain them on uncertain failure. */
	ret = apple_dart_sync(priv);
	if (ret)
		return ret;

	/* Enable all streams. */
	for (i = 0; i < DIV_ROUND_UP(priv->nsid, 32); i++)
		writel(~0, priv->base + DART_SID_ENABLE(priv, i));

	/* Enable translations. */
	for (sid = 0; sid < priv->nsid; sid++) {
		writel(priv->tcr_translate_enable,
		       priv->base + DART_TCR(priv, sid));
	}

	return 0;
}

static int apple_dart_remove(struct udevice *dev)
{
	struct apple_dart_priv *priv = dev_get_priv(dev);
	int sid, i, ret;

	if (priv->error)
		return priv->error;

	/* Disable translations. */
	for (sid = 0; sid < priv->nsid; sid++)
		writel(0, priv->base + DART_TCR(priv, sid));

	/* Remove page tables. */
	for (sid = 0; sid < priv->nsid; sid++) {
		for (i = 0; i < priv->nttbr; i++)
			writel(0, priv->base + DART_TTBR(priv, sid, i));
	}
	ret = apple_dart_sync(priv);
	if (ret)
		return ret;

	io_lmb_teardown(&priv->io_lmb);

	return 0;
}


static struct apple_dart_priv p;
static struct udevice dev={&p,&apple_dart_ops,"apple,t8103-dart"};
static unsigned cases;
static void fixture(void){
 free(p.l1);free(p.l2);memset(&p,0,sizeof(p));memset(regs,0,sizeof(regs));
 flushes=fail_flush=delay_reads=reads=mmio_writes=clock_us=0;force_translation=false;dev.compat="apple,t8103-dart";
}
static void passed(const char*s){cases++;printf("PASS %s\n",s);}
int main(void){
 fixture();assert(!apple_dart_probe(&dev));assert(flushes==2);assert(!apple_dart_get_error(&dev));
 dma_addr_t a=apple_dart_map(&dev,(void*)0x100123,17000);assert(a==0x4123&&p.io_lmb.reserved);
 apple_dart_unmap(&dev,a,17000);assert(!p.io_lmb.reserved&&p.io_lmb.frees==1);
 assert(!apple_dart_remove(&dev));assert(p.io_lmb.teardowns==1);passed("normal mapping/unmapping/remove");
 fixture();delay_reads=9;assert(!apple_dart_probe(&dev));assert(clock_us==18);passed("delayed flush completes within deadline");
 fixture();fail_flush=1;assert(apple_dart_probe(&dev)==-ETIMEDOUT);assert(clock_us<=1002);assert(!p.l1&&!p.l2&&p.io_lmb.teardowns==1);passed("first probe timeout bounded before allocations");
 fixture();fail_flush=2;assert(apple_dart_probe(&dev)==-ETIMEDOUT);assert(p.l1&&p.l2&&p.io_lmb.teardowns==0);assert(!readl(regs+0x100));passed("second probe timeout retains hardware-visible tables; streams not enabled");
 fixture();assert(!apple_dart_probe(&dev));fail_flush=3;assert(!apple_dart_map(&dev,(void*)0x100000,16384));assert(p.io_lmb.reserved&&p.io_lmb.frees==0);assert(apple_dart_get_error(&dev)==-ETIMEDOUT);passed("map timeout returns failure and quarantines IOVA");
 unsigned writes=mmio_writes,allocs=p.io_lmb.allocs;
 fail_flush=0;assert(!apple_dart_map(&dev,(void*)0x200000,16384));assert(mmio_writes==writes&&p.io_lmb.allocs==allocs);passed("latched map fault does not retry after hardware recovery");
 apple_dart_unmap(&dev,16384,16384);assert(p.io_lmb.reserved&&mmio_writes==writes);assert(apple_dart_remove(&dev)==-ETIMEDOUT&&p.io_lmb.teardowns==0);passed("faulted unmap/remove cannot recycle resources");
 fixture();assert(!apple_dart_probe(&dev));a=apple_dart_map(&dev,(void*)0x200000,16384);assert(a);fail_flush=4;apple_dart_unmap(&dev,a,16384);assert(apple_dart_get_error(&dev)==-ETIMEDOUT);assert(p.io_lmb.reserved&&p.io_lmb.frees==0);passed("unmap timeout observable and IOVA retained");
 fixture();assert(!apple_dart_probe(&dev));fail_flush=3;assert(apple_dart_remove(&dev)==-ETIMEDOUT);assert(p.l1&&p.l2&&p.io_lmb.teardowns==0);passed("remove timeout retains resources");
 fixture();dev.compat="apple,t8110-dart";writel(16,regs+0xc);assert(!apple_dart_probe(&dev));assert(last_cmd_offset==0x80&&last_cmd_value==0);passed("T8110 flush-all command address and encoding");
 fixture();dev.compat="apple,t8110-dart";writel(16,regs+0xc);fail_flush=1;assert(apple_dart_probe(&dev)==-ETIMEDOUT);assert(clock_us<=1002);passed("T8110 permanent BUSY bounded");
 fixture();writel(1,regs+4);assert(!apple_dart_probe(&dev));assert(p.bypass);a=apple_dart_map(&dev,(void*)0x123456,123);assert(a==0x123456);assert(!apple_dart_remove(&dev));passed("existing bypass success unchanged");
 fixture();assert(apple_dart_get_error(NULL)==-EINVAL);const void*save=dev.ops;dev.ops=NULL;assert(apple_dart_get_error(&dev)==-EINVAL);dev.ops=save;passed("status rejects wrong device");
 fixture();force_translation=true;writel(1,regs+4);assert(!apple_dart_probe(&dev));assert(!p.bypass&&p.l1);assert(!apple_dart_limit_stream(&dev,1));for(unsigned i=0;i<16;i++)assert(readl(regs+0x100+i*4)==(i==1?BIT(7):0));assert(readl(regs+0xfc)==BIT(1));passed("force translation despite bypass capability; only SID1 enabled");
 writes=mmio_writes;assert(apple_dart_limit_stream(&dev,16)==-EINVAL);assert(mmio_writes==writes);passed("invalid stream rejected before writes");
 fail_flush=flushes+1;assert(apple_dart_limit_stream(&dev,1)==-ETIMEDOUT);assert(apple_dart_get_error(&dev)==-ETIMEDOUT);for(unsigned i=0;i<16;i++)assert(!readl(regs+0x100+i*4));passed("stream-limit invalidation timeout leaves streams disabled");
 fixture();printf("cases=%u failures=0\n",cases);return 0;
}
