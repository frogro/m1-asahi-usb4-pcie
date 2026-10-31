
// SPDX-License-Identifier: GPL-2.0-only
/* Extracted NHI guard functions, host OF/MMIO mocks. No hardware access.
 * Copyright The Asahi Linux Contributors; Sven Peter <sven@kernel.org>.
 */
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <assert.h>
typedef unsigned long long u64;typedef uint32_t u32;typedef int ofnode;
#define BIT(n) (1U<<(n))
#define DART_PATH "dart"
#define NHI_PATH "nhi"
#define DART_BASE 0x501a80000ULL
#define NHI_BASE 0x501f00000ULL
struct resource {u64 start,end;};
struct ofnode_phandle_args {ofnode node;unsigned args_count,args[1];};
static int bad,reads;
static u32 regs[0x100000/4];
static ofnode ofnode_root(void){return 0;}
static ofnode ofnode_path(const char*s){return !strcmp(s,"dart")?1:2;}
static bool ofnode_device_is_compatible(ofnode n,const char*c){return bad!=n+1;}
static bool ofnode_is_enabled(ofnode n){return bad==n+3;}
static bool ofnode_read_bool(ofnode n,const char*k){return bad!=6;}
static int ofnode_read_resource(ofnode n,int i,struct resource*r){if(bad==7)return -EINVAL;r->start=DART_BASE+(bad==8?4:0);r->end=r->start+0x4000-1+(bad==9?4:0);return 0;}
static int ofnode_read_resource_byname(ofnode n,const char*k,struct resource*r){if(!strcmp(k,"pdf")){if(bad==20)return -EINVAL;r->start=0x501db0000ULL+(bad==18?4:0);r->end=r->start+0x30004-1+(bad==19?4:0);return 0;}if(bad==10)return -EINVAL;r->start=NHI_BASE+(bad==11?4:0);r->end=r->start+0x100000-1+(bad==12?4:0);return 0;}
static u64 resource_size(struct resource*r){return r->end-r->start+1;}
static int ofnode_parse_phandle_with_args(ofnode n,const char*a,const char*b,int c,int d,struct ofnode_phandle_args*r){if(bad==13)return -EINVAL;r->node=bad==14?2:1;r->args_count=bad==15?0:1;r->args[0]=bad==16?0:1;return 0;}
static bool ofnode_equal(ofnode a,ofnode b){return a==b;}
static void*map_sysmem(u64 a,unsigned n){assert(a==NHI_BASE&&n==0x100000);return regs;}
static u32 readl(void*p){reads++;return *(u32*)p;}
static int exact_resource(ofnode node, const char *name, u64 addr, u64 size)
{
	struct resource res;
	int ret = name ? ofnode_read_resource_byname(node, name, &res) :
			 ofnode_read_resource(node, 0, &res);

	if (ret)
		return ret;
	return res.start == addr && resource_size(&res) == size ? 0 : -ERANGE;
}

int apple_nhi_m1_check(void)
{
	ofnode node = ofnode_path(DART_PATH), nhi = ofnode_path(NHI_PATH);
	struct ofnode_phandle_args args;
	int ret;

	if (!ofnode_device_is_compatible(ofnode_root(), "apple,j274") ||
	    !ofnode_device_is_compatible(node, "apple,t8103-dart") ||
	    !ofnode_device_is_compatible(nhi, "apple,t8103-usb4-nhi") ||
	    ofnode_is_enabled(node) || ofnode_is_enabled(nhi) ||
	    !ofnode_read_bool(node, "u-boot,force-dart-translation"))
		return -ENODEV;
	ret = exact_resource(node, NULL, DART_BASE, 0x4000);
	if (ret)
		return ret;
	ret = exact_resource(nhi, "nhi", NHI_BASE, 0x100000);
	if (ret)
		return ret;
	ret = ofnode_parse_phandle_with_args(nhi, "iommus", "#iommu-cells",
					   0, 0, &args);
	if (ret || args.args_count != 1 || args.args[0] != 1 ||
	    !ofnode_equal(args.node, node))
		return -EINVAL;
	return 0;
}

int apple_nhi_m1_control_check(void)
{
	return exact_resource(ofnode_path(NHI_PATH), "pdf", 0x501db0000ULL, 0x30004);
}

/* Same BE32 offset/clear-mask/set-value format as Linux apple_tunable.
 * Validate BOTH groups before power or MMIO, then revalidate before applying.
 */
/* Only called after ACIO firmware is ready and power is held. */
static int rings_idle(void)
{
	void *nhi = map_sysmem(NHI_BASE, 0x100000);
	u32 value;
	int i;

	for (i = 0; i < 12; i++) {
		value = readl(nhi + 0x10000 + i * 0x4000 + 0x10);
		if (value == 0xffffffff || (value & BIT(31)))
			return -EBUSY;
		value = readl(nhi + 0x80000 + i * 0x4000 + 0x10);
		if (value == 0xffffffff || (value & BIT(31)))
			return -EBUSY;
	}
	return 0;
}

/* Probe13 observed 0x80080 on all cold streams. Do not treat this alone
 * as ownership: accept only that exact state or disabled TCR, and require
 * every TTBR to be invalid. Active/unknown mappings must never be replaced.
 * The caller also proves all NHI rings disabled before touching this DART.
 */
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


int main(void){unsigned cases=0;assert(!apple_nhi_m1_check());assert(!reads);cases++;
 for(bad=1;bad<=16;bad++){assert(apple_nhi_m1_check()<0);assert(!reads);cases++;}
 bad=0;assert(!rings_idle());assert(reads==24);cases++;
 unsigned offsets[]={0x10010,0x80010,0x10010+11*0x4000,0x80010+11*0x4000};
 for(unsigned i=0;i<4;i++){memset(regs,0,sizeof(regs));regs[offsets[i]/4]=BIT(31);assert(rings_idle()==-EBUSY);cases++;}
 memset(regs,0,sizeof(regs));regs[0x10010/4]=0xffffffff;assert(rings_idle()==-EBUSY);cases++;
 memset(regs,0,sizeof(regs));assert(!empty_translation(regs));cases++;
 for(unsigned i=0;i<16;i++)regs[(0x100+i*4)/4]=0x80080;
 assert(!empty_translation(regs));cases++;
 for(unsigned i=0;i<64;i++){regs[(0x200+i*4)/4]=BIT(31);assert(empty_translation(regs)==-EBUSY);regs[(0x200+i*4)/4]=0;cases++;}
 for(unsigned i=0;i<16;i++){regs[(0x100+i*4)/4]=BIT(8);assert(empty_translation(regs)==-EBUSY);regs[(0x100+i*4)/4]=0x80080;cases++;}
 regs[0x20/4]=BIT(2);assert(empty_translation(regs)==-EBUSY);cases++;
 regs[0x20/4]=0xffffffff;assert(empty_translation(regs)==-EBUSY);cases++;
 bad=0;reads=0;assert(!apple_nhi_m1_control_check());assert(!reads);cases++;
 for(bad=18;bad<=20;bad++){assert(apple_nhi_m1_control_check()<0);assert(!reads);cases++;}
 printf("NHI preflight/idle guards: %u cases, zero failures\n",cases);return 0;
}
