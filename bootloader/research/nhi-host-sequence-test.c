
// SPDX-License-Identifier: GPL-2.0-only
/* ACIO/NHI diagnostic production function with host-only dependency mocks.
 * Derived from Asahi Linux; Copyright The Asahi Linux Contributors,
 * Copyright (c) Sven Peter <sven@kernel.org>.
 */
#include <stdint.h>
#include <stdbool.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <assert.h>
typedef uint32_t u32;typedef unsigned long long u64;typedef uint64_t dma_addr_t;
#define SZ_16K 16384
#define BIT(n) (1U<<(n))
#define DART_BASE 0x501a80000ULL
#define DART_PATH "dart"
#define DM_REMOVE_NORMAL 0
struct udevice {int unused;};
struct iommu_ops {dma_addr_t(*map)(struct udevice*,void*,size_t);void(*unmap)(struct udevice*,dma_addr_t,size_t);};
static struct udevice device;
static struct {void*dm_root;} g;
#define gd (&g)
static unsigned char regs[0x4000];
static int count,fail_at,error,limited,allocated,freed,removed,mapped,unmapped;
static void *allocation;
static dma_addr_t map_result=0x4000;
static int step(void){return ++count==fail_at?-EIO:0;}
static void*map_sysmem(u64 a,unsigned n){return regs;}
static int apple_nhi_m1_check(void){return step();}
static int rings_idle(void){return step();}
static int control_calls;
static int apple_nhi_m1_control_read(struct udevice*d){assert(limited&&!allocated&&!removed);control_calls++;return step();}
static int apple_nhi_m1_tunables_apply(bool n){assert(n);return step();}
static u32 readl(void*p){unsigned off=(unsigned char*)p-regs; if(limited&&off>=0x100&&off<0x140)return off==0x104?BIT(7):0;return 0;}
static int ofnode_path(const char*s){return 0;}
static void*lists_driver_lookup_name(const char*s){return &device;}
static int lists_bind_fdt(void*a,int b,struct udevice**d,void*c,bool e){*d=&device;return step();}
static int device_probe(struct udevice*d){return step();}
static int apple_dart_limit_stream(struct udevice*d,unsigned sid){assert(sid==1);limited=1;return step();}
static void *test_memalign(unsigned a,size_t n){if(step())return NULL;allocation=malloc(n);allocated=1;return allocation;}
#define memalign test_memalign
static void test_free(void*p){assert(p==allocation);freed++;free(p);allocation=NULL;}
#define free test_free
static dma_addr_t map(struct udevice*d,void*p,size_t n){assert(p==allocation);mapped++;if(step()){error=-ETIMEDOUT;return 0;}return map_result;}
static void unmap(struct udevice*d,dma_addr_t a,size_t n){unmapped++;if(step())error=-ETIMEDOUT;}
static const struct iommu_ops ops={map,unmap};
static const void*device_get_ops(struct udevice*d){return &ops;}
static int apple_dart_get_error(struct udevice*d){return error;}
static int device_remove(struct udevice*d,int flags){removed++;return step();}
static int empty_translation(void *regs)
{
	u32 value;
	int sid, index, ret = 0;

	for (sid = 0; sid < 16; sid++) {
		value = readl(regs + 0x100 + sid * 4);
		printf("NHI DART initial TCR[%d]=%#x\n", sid, value);
		if (value != 0 && value != 0x80080)
			ret = -EBUSY;
		for (index = 0; index < 4; index++) {
			value = readl(regs + 0x200 + sid * 16 + index * 4);
			if (value & BIT(31)) {
				printf("NHI DART valid TTBR[%d,%d]=%#x\n", sid, index, value);
				ret = -EBUSY;
			}
		}
	}
	value = readl(regs + 0x20);
	if (value == 0xffffffff || (value & BIT(2)))
		ret = -EBUSY;
	if (!ret)
		puts("NHI DART initial tables empty; no inherited mapping\n");
	return ret;
}

int apple_nhi_m1_dart_test(unsigned int stage)
{
	struct udevice *dart = NULL;
	const struct iommu_ops *ops;
	void *regs = map_sysmem(DART_BASE, 0x4000);
	void *buffer = NULL;
	dma_addr_t dva;
	u32 value;
	int i, ret;

	ret = apple_nhi_m1_check();
	if (ret)
		return ret;
	ret = rings_idle();
	if (ret)
		return ret;
	value = readl(regs + 0x60);
	printf("NHI DART config=%#x params2=%#x\n", value, readl(regs + 4));
	if (value == 0xffffffff || (value & BIT(15)))
		return -EBUSY;
	ret = empty_translation(regs);
	if (ret)
		return ret;
	ret = lists_bind_fdt(gd->dm_root, ofnode_path(DART_PATH), &dart,
			    lists_driver_lookup_name("apple_dart"), false);
	if (ret || !dart)
		return ret ? ret : -ENODEV;
	ret = device_probe(dart);
	if (ret)
		return ret;
	ret = apple_dart_limit_stream(dart, 1);
	if (ret)
		return ret;
	for (i = 0; i < 16; i++) {
		if (readl(regs + 0x100 + i * 4) != (i == 1 ? BIT(7) : 0))
			return -EIO;
	}
	puts("NHI DART stream1 translation enabled; all other streams disabled\n");
	if (stage >= 3) {
		ret = apple_nhi_m1_tunables_apply(true);
		if (!ret)
			ret = rings_idle();
		if (ret)
			return ret;
		puts("NHI-TUNABLES PASS; all rings remain disabled\n");
	}
	if (stage >= 4)
		return apple_nhi_m1_control_read(dart);
	ops = device_get_ops(dart);
	buffer = memalign(SZ_16K, 2 * SZ_16K);
	if (!buffer)
		return -ENOMEM;
	memset(buffer, 0xa5, 2 * SZ_16K);
	dva = ops->map(dart, buffer, 2 * SZ_16K);
	ret = apple_dart_get_error(dart);
	/* On any uncertain failure retain the buffer until mandatory reset. */
	if (ret)
		return ret;
	if (!dva) {
		free(buffer);
		return -ENOMEM;
	}
	printf("NHI DART mapped size=%#x iova=%llx\n", 2 * SZ_16K, (u64)dva);
	if (dva < SZ_16K || dva > 0x100000000ULL - 3 * SZ_16K ||
	    (dva & (SZ_16K - 1)))
		return -ERANGE;
	ret = rings_idle();
	if (ret)
		return ret;
	ops->unmap(dart, dva, 2 * SZ_16K);
	ret = apple_dart_get_error(dart);
	if (ret)
		return ret;
	free(buffer);
	ret = device_remove(dart, DM_REMOVE_NORMAL);
	if (ret)
		return ret;
	puts("NHI-DART-MAP PASS; map/unmap/remove only, no DMA issued\n");
	return 0;
}
#undef free
static void fixture(void){free(allocation);allocation=NULL;count=error=limited=allocated=freed=removed=mapped=unmapped=0;map_result=0x4000;}
int main(void){unsigned cases=0;int ret,total;
 fixture();fail_at=0;assert(!apple_nhi_m1_dart_test(2));assert(freed==1&&removed==1&&unmapped==1);total=count;cases++;
 for(int i=1;i<=total;i++){
  fixture();fail_at=i;ret=apple_nhi_m1_dart_test(2);assert(ret<0);
  if(error){assert(!freed&&!removed);}
  if(mapped&&!unmapped)assert(!freed&&!removed);
  if(removed)assert(freed==1&&unmapped==1);
  cases++;
 }
 fixture();fail_at=0;map_result=0;assert(apple_nhi_m1_dart_test(2)==-ENOMEM);assert(freed==1&&!removed);cases++;
 fixture();map_result=1;assert(apple_nhi_m1_dart_test(2)==-ERANGE);assert(!freed&&!removed);cases++;
 fixture();fail_at=0;assert(!apple_nhi_m1_dart_test(3));assert(freed==1&&removed==1);total=count;cases++;
 for(int i=1;i<=total;i++){fixture();fail_at=i;assert(apple_nhi_m1_dart_test(3)<0);if(error)assert(!freed&&!removed);if(mapped&&!unmapped)assert(!freed&&!removed);cases++;}
 fixture();fail_at=0;assert(!apple_nhi_m1_dart_test(4));assert(control_calls==1&&!allocated&&!removed);total=count;cases++;
 for(int i=1;i<=total;i++){fixture();fail_at=i;assert(apple_nhi_m1_dart_test(4)<0);assert(!freed&&!removed);cases++;}
 fixture();printf("NHI DART lifecycle: %u cases, zero failures; no hardware DMA\n",cases);return 0;
}
