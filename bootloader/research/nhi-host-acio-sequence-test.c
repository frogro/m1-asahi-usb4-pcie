
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <assert.h>
typedef uint32_t u32;
#define BIT(n) (1U<<(n))
#define GENMASK(h,l) ((~0U >> (31-(h))) & (~0U << (l)))
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
#define ACIO_NODE "acio"
#define MBOX_NODE "mbox"
#define UCLASS_POWER_DOMAIN 1
#define UCLASS_RESET 2
#define APPLE_RTKIT_PWR_STATE_ON 32
#define APPLE_RTKIT_PWR_STATE_SLEEP 1
struct udevice {int unused;};
struct reset_ctl {struct udevice *dev;};
struct mbox_chan {int unused;};
struct apple_rtkit {int unused;};
static struct udevice device;
static struct apple_rtkit rtkit;
static struct {struct udevice *dm_root;} globals;
#define gd (&globals)
static const u32 domains[]={0x458,0x460,0x468,0x450};
static bool used;
static unsigned calls,fail_at,ntrace,frees;
static const char *trace[64];
static u32 reset_state, nhi_cap = 12;
static u32 readl(void*p){return nhi_cap;}
static unsigned char memory[0xc000];
static int reset_io;
static int shmem_setup,shmem_destroy;
static int dart_fail;
static int tune_fail;
static int apple_nhi_m1_tunables_apply(bool nhi){assert(!nhi);trace[ntrace++]="rc_tune";return tune_fail?-EIO:0;}
static unsigned last_stage;
static int apple_nhi_m1_dart_test(unsigned stage){last_stage=stage;trace[ntrace++]="dart_test";return dart_fail?-EIO:0;}
static int step(const char *name) {trace[ntrace++]=name;return ++calls==fail_at?-EIO:0;}
static void *map_sysmem(uint64_t p,unsigned n){return memory;}
static int ofnode_path(const char *p){return 0;}
static int pdnode(u32 off){return 0;}
static int apple_acio_m1_check(void){return step("check");}
static int domain_on(u32 off){char const*n=off==0x448?"common":off==0x458?"cio":off==0x460?"cio_pcie":off==0x468?"cio_usb":"pcie";return step(n);}
static int uclass_get_device_by_ofnode(int cl,int n,struct udevice**d){*d=&device;return step(cl==1?"get_pd":"get_reset");}
static int reset_request(struct reset_ctl*r){return step("request_reset");}
static int reset_assert(struct reset_ctl*r){int e=step("assert_reset");if(!e)reset_state=BIT(31)|BIT(10);return e;}
static int reset_deassert(struct reset_ctl*r){int e=step("deassert_reset");if(!e)reset_state=0;return e;}
static u32 pdstate(u32 off){return reset_state;}
static void udelay(unsigned us){assert(us==2);}
static int acio_m1_deassert(void*a,void*b,int port,unsigned size,u32*s){assert(port==1&&size==0x8000);*s=4;return step("acio_reset");}
static int device_bind_driver_to_node(void*a,const char*b,const char*c,int n,struct udevice**d){*d=&device;return step("bind_owner");}
static void *lists_driver_lookup_name(const char*n){return &device;}
static int lists_bind_fdt(void*a,int n,struct udevice**d,void*b,bool c){*d=&device;return step("bind_mbox");}
static int mbox_get_by_index(void*d,int n,struct mbox_chan*c){return step("get_mbox");}
static void writel(u32 v,void*p){assert(v==BIT(1));trace[ntrace++]="m3_start";}
static struct apple_rtkit *apple_rtkit_init(void*a,void*b,int c,int d){return step("rtkit_init")?NULL:&rtkit;}
static int apple_rtkit_boot(struct apple_rtkit*r){return step("boot");}
static int apple_rtkit_set_ap_power(struct apple_rtkit*r,int v){assert(v==32);return step("ap_on");}
static int ready(u32*s){*s=0x1000000;return step("ready");}
#define readl_poll_sleep_timeout(addr,val,cond,delay,timeout) ready(&(val))
static int apple_rtkit_shutdown(struct apple_rtkit*r,int v){assert(v==1);return step("shutdown");}
static void apple_rtkit_free(struct apple_rtkit*r){frees++;}
int apple_acio_m1_start(unsigned int stage)
{
 struct udevice *pd, *rstdev, *owner, *mbox;
 struct reset_ctl rst = {};
 struct mbox_chan chan = {};
 struct apple_rtkit *rtk = NULL;
 void *rc = map_sysmem(0x501ac0000ULL, 0xc000);
 u32 state = 0;
 int i, ret, shutdown;

 ret = apple_acio_m1_check();
 if (ret) return ret;
 used = true; /* Any partial start requires a whole-machine reset, no retry. */
 ret = domain_on(0x448);
 if (ret) goto out;
 ret = uclass_get_device_by_ofnode(UCLASS_POWER_DOMAIN, pdnode(0x450), &pd);
 if (ret) goto out;
 ret = uclass_get_device_by_ofnode(UCLASS_RESET, pdnode(0x450), &rstdev);
 if (ret) goto out;
 rst.dev = rstdev;
 ret = reset_request(&rst);
 if (!ret) ret = reset_assert(&rst);
 if (ret) goto out;
 state = pdstate(0x450);
 if ((state & (BIT(31) | BIT(10))) != (BIT(31) | BIT(10))) { ret = -EIO; goto out; }
 udelay(2);
 ret = reset_deassert(&rst);
 if (ret) goto out;
 state = pdstate(0x450);
 if (state & (BIT(31) | BIT(10))) { ret = -EIO; goto out; }
 puts("ACIO PCIe-C reset-before-power PASS\n");
 for (i = 0; i < ARRAY_SIZE(domains); i++) {
  ret = domain_on(domains[i]);
  if (ret) goto out;
 }
 ret = acio_m1_deassert(&reset_io, map_sysmem(0x23b784000ULL, 0x8000),
                       1, 0x8000, &state);
 printf("ACIO reset status=%#x ret=%d\n", state, ret);
 if (ret) goto out;
 ret = device_bind_driver_to_node(gd->dm_root, "apple-acio-diagnostic",
                                  "acio-port1-diagnostic", ofnode_path(ACIO_NODE), &owner);
 if (ret) goto out;
 ret = lists_bind_fdt(gd->dm_root, ofnode_path(MBOX_NODE), &mbox,
                      lists_driver_lookup_name("apple-mbox"), false);
 if (!ret && !mbox) ret = -ENODEV;
 if (ret) goto out;
 /* Explicit binding must set the same compatible match-data as normal scan. */
 ret = mbox_get_by_index(owner, 0, &chan);
 if (ret) goto out;
 puts("ACIO M3 start\n");
 writel(BIT(1), rc + 0xc);
 rtk = apple_rtkit_init(&chan, NULL, shmem_setup, shmem_destroy);
 if (!rtk) { ret = -ENOMEM; goto out; }
 ret = apple_rtkit_boot(rtk);
 printf("ACIO RTKit boot ret=%d\n", ret);
 if (ret) goto out;
 ret = apple_rtkit_set_ap_power(rtk, APPLE_RTKIT_PWR_STATE_ON);
 printf("ACIO RTKit AP-on ret=%d\n", ret);
 if (ret) goto out;
 ret = readl_poll_sleep_timeout(rc + 0xa8, state, state != 0xffffffff && (state & GENMASK(30,24)), 100, 500000);
 printf("ACIO firmware state=%#x ret=%d\n", state, ret);
 if (!ret) puts("ACIO M3 READY PASS; no NHI/tunnel/DMA\n");
 if (!ret && stage >= 1) {
  u32 cap = readl(map_sysmem(0x501f00000ULL, 4));
  printf("ACIO NHI HOP_COUNT raw=%#x count=%u\n", cap, cap & 0x3ff);
  /* J274 NHI has 12 TX/RX ring pairs in the tested Linux DT. No writes. */
  if (cap == 0xffffffff || (cap & 0x3ff) != 12)
   ret = -EPROTO;
  else
   puts("NHI-READONLY PASS; no configuration, rings or DMA\n");
 }
 if (!ret && stage >= 3) ret = apple_nhi_m1_tunables_apply(false);
 if (!ret && stage >= 2) ret = apple_nhi_m1_dart_test(stage);
 shutdown = apple_rtkit_shutdown(rtk, APPLE_RTKIT_PWR_STATE_SLEEP);
 printf("ACIO RTKit shutdown ret=%d\n", shutdown);
 if (!ret) ret = shutdown;
out:
 if (rtk) apple_rtkit_free(rtk);
 printf("ACIO diagnostic ret=%d; power held until mandatory full reset\n", ret);
 return ret;
}

int main(void){
 unsigned total, cases=0;int ret;
 ret=apple_acio_m1_start(false);assert(!ret);total=calls;cases++;
 const char *expected[]={"check","common","get_pd","get_reset","request_reset","assert_reset","deassert_reset","cio","cio_pcie","cio_usb","pcie","acio_reset","bind_owner","bind_mbox","get_mbox","m3_start","rtkit_init","boot","ap_on","ready","shutdown"};
 assert(ntrace==ARRAY_SIZE(expected));for(unsigned i=0;i<ntrace;i++)assert(!strcmp(trace[i],expected[i]));assert(frees==1);
 for(unsigned i=1;i<=total;i++){
  fail_at=i;calls=ntrace=frees=0;reset_state=0;used=false;
  ret=apple_acio_m1_start(false);assert(ret<0);
  /* Ready failure still performs the documented firmware shutdown. */
  assert(calls==i || (i==total-1 && calls==total));
  if(i<=15)for(unsigned j=0;j<ntrace;j++)assert(strcmp(trace[j],"m3_start"));
  cases++;
 }
 for(unsigned i=0;i<4;i++) {
  fail_at=calls=ntrace=frees=0;reset_state=0;used=false;
  nhi_cap=(u32[]){12,0,0xffffffff,16}[i];
  ret=apple_acio_m1_start(true);
  assert(i==0 ? ret==0 : ret==-EPROTO);
  assert(!strcmp(trace[ntrace-1],"shutdown") && frees==1);cases++;
 }
 for(unsigned i=0;i<2;i++) {
  fail_at=calls=ntrace=frees=0;reset_state=0;used=false;nhi_cap=12;dart_fail=i;
  ret=apple_acio_m1_start(2);assert(i?ret==-EIO:ret==0);
  assert(!strcmp(trace[ntrace-2],"dart_test")&&!strcmp(trace[ntrace-1],"shutdown"));cases++;
 }
 for(unsigned i=0;i<3;i++) {
  fail_at=calls=ntrace=frees=0;reset_state=0;used=false;nhi_cap=12;tune_fail=i==1;dart_fail=i==2;
  ret=apple_acio_m1_start(3);assert(i?ret==-EIO:ret==0);
  assert(!strcmp(trace[ntrace-1],"shutdown")&&frees==1);
  if(i==1)assert(!strcmp(trace[ntrace-2],"rc_tune"));else assert(!strcmp(trace[ntrace-3],"rc_tune")&&!strcmp(trace[ntrace-2],"dart_test"));cases++;
 }
 for(unsigned i=0;i<2;i++) {
  fail_at=calls=ntrace=frees=0;reset_state=0;used=false;nhi_cap=12;tune_fail=0;dart_fail=i;
  ret=apple_acio_m1_start(4);assert(i?ret==-EIO:ret==0);assert(last_stage==4);
  assert(!strcmp(trace[ntrace-1],"shutdown")&&frees==1);cases++;
 }
 printf("ACIO production-sequence mock: %u cases, zero failures; no hardware access\n",cases);
 return 0;
}
