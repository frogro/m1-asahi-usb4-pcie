#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef uint32_t u32;
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
struct atc_m1_hw {void *xhci; u32 cap;};
static unsigned n;
static uintptr_t base;
static const unsigned expected[]={0xc110,0xc11c,0xc120,0xc12c,0xc140,0xc144,0xc14c,0xc200,0xc2c0,0xc630,0xcd38,0xcd3c,0xcd40};
static u32 readl(void *p) {
 uintptr_t off=(uintptr_t)p-base;
 if(n<13 && off!=expected[n]) abort();
 if(n>=13 && off!=0x20 && off!=0x24) abort();
 n++; return 0x12345678;
}
static void snapshot_dwc3(struct atc_m1_hw *hw, const char *phase)
{
 static const u32 offsets[] = {
  0xc110, 0xc11c, 0xc120, 0xc12c, 0xc140, 0xc144, 0xc14c,
  0xc200, 0xc2c0, 0xc630, 0xcd38, 0xcd3c, 0xcd40,
 };
 unsigned int i;

 for (i = 0; i < ARRAY_SIZE(offsets); i++)
  printf("DWC3-SNAPSHOT %s reg[%#x]=%#x\n", phase, offsets[i],
         readl(hw->xhci + offsets[i]));
 printf("DWC3-SNAPSHOT %s command=%#x status=%#x\n", phase,
        readl(hw->xhci + hw->cap), readl(hw->xhci + hw->cap + 4));
}


int main(void) {
 char *mem=calloc(1,0x10000); if(!mem)return 1;
 struct atc_m1_hw h={.xhci=mem,.cap=0x20};base=(uintptr_t)mem;
 const char *phases[]={"before-remove","before-acio","after-acio"};
 for(unsigned i=0;i<3;i++){n=0;snapshot_dwc3(&h,phases[i]);if(n!=15)abort();}
 free(mem);puts("3 phases, 45 allowlisted reads, no writes");return 0;
}
