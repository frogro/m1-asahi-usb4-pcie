#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <assert.h>
typedef uint32_t u32;
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
enum { ATC_CORE, ATC_PIPE, ATC_USB2 };
struct atc_m1_hw {void *base[3];};
static struct atc_m1_hw h;
static unsigned n;
static const unsigned expected[][2]={{0,8},{0,72},{0,76},{0,432},{0,2052},{0,2560},{0,2564},{0,2592},{0,2676},{0,4116},{0,4136},{0,8192},{0,8704},{0,8712},{0,8724},{0,8736},{0,8740},{0,10752},{0,10784},{0,10808},{0,10916},{0,36880},{0,37104},{0,45056},{0,45060},{0,45100},{0,45104},{0,45108},{0,45128},{0,45140},{0,45152},{0,53248},{0,53252},{0,53256},{0,65552},{0,65776},{0,73728},{0,73732},{0,73772},{0,73776},{0,73780},{0,73800},{0,73812},{0,73824},{0,81920},{0,81924},{0,81928},{0,131072},{0,131076},{0,131080},{1,0},{1,4},{1,12},{1,16},{1,20},{1,28},{1,32},{2,0},{2,4},{2,8},{2,28}};
static u32 readl(void*p){assert(n<ARRAY_SIZE(expected));unsigned b=expected[n][0],o=expected[n][1];assert(p==h.base[b]+o);n++;return 0x12345678;}
static void snapshot_phy_extended(void *context)
{
 struct atc_m1_hw *hw = context;
 static const u32 core[] = { 0x8, 0x48, 0x4c, 0x1b0, 0x804, 0xa00, 0xa04, 0xa20, 0xa74, 0x1014, 0x1028, 0x2000, 0x2200, 0x2208, 0x2214, 0x2220, 0x2224, 0x2a00, 0x2a20, 0x2a38, 0x2aa4, 0x9010, 0x90f0, 0xb000, 0xb004, 0xb02c, 0xb030, 0xb034, 0xb048, 0xb054, 0xb060, 0xd000, 0xd004, 0xd008, 0x10010, 0x100f0, 0x12000, 0x12004, 0x1202c, 0x12030, 0x12034, 0x12048, 0x12054, 0x12060, 0x14000, 0x14004, 0x14008, 0x20000, 0x20004, 0x20008 };
 static const u32 pipe[] = { 0x0, 0x4, 0xc, 0x10, 0x14, 0x1c, 0x20 };
 static const u32 usb2[] = { 0x0, 0x4, 0x8, 0x1c };
 unsigned int i;
 for (i = 0; i < ARRAY_SIZE(core); i++)
  printf("ATC-EXTENDED core[%#x]=%#x\n", core[i], readl(hw->base[ATC_CORE] + core[i]));
 for (i = 0; i < ARRAY_SIZE(pipe); i++)
  printf("ATC-EXTENDED pipe[%#x]=%#x\n", pipe[i], readl(hw->base[ATC_PIPE] + pipe[i]));
 for (i = 0; i < ARRAY_SIZE(usb2); i++)
  printf("ATC-EXTENDED usb2[%#x]=%#x\n", usb2[i], readl(hw->base[ATC_USB2] + usb2[i]));
}

int main(void){for(unsigned i=0;i<3;i++){h.base[i]=calloc(1,0x40000);assert(h.base[i]);}snapshot_phy_extended(&h);assert(n==61);for(unsigned i=0;i<3;i++)free(h.base[i]);puts("61 allowlisted reads, no writes; zero failures");}
