#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
typedef uint32_t u32;
#define BIT(n) (1U<<(n))
#define ATC_CORE_READY 99
struct atc_m1_hw {void *xhci; unsigned stage; int hostrun;};
static u32 mem[0x10000/4];
static unsigned reads,writes,fail_read,halt_calls,fail_halt;
static unsigned order[]={0xcd38,0xcd3c,0xcd40,0xc2c0,0xc200,0xc110,0xc200,0xc2c0};
static u32 readl(void *p){reads++;if(fail_read==reads)return 0xffffffff;return *(u32*)p;}
static void writel(u32 v,void *p){uintptr_t off=(uintptr_t)p-(uintptr_t)mem;if(writes>=8||off!=order[writes])abort();writes++;*(u32*)p=v;}
static int hw_verify_halted(struct atc_m1_hw *h){(void)h;return ++halt_calls==fail_halt?-EBUSY:0;}
static void init(void){memset(mem,0,sizeof(mem));reads=writes=halt_calls=fail_read=fail_halt=0;mem[0xc120/4]=0x33313130;mem[0xc140/4]=0x4020800a;mem[0xc110/4]=0x30c12004;mem[0xc200/4]=0x102400;mem[0xc2c0/4]=0x1021102;mem[0xcd40/4]=0x3c20060c;}

#define CONFIG_IS_ENABLED(x) 1
#define DWC3_REG_OFFSET 0xc100
struct dwc3 {int unused;};
static int dart_ret,core_ret,core_calls;
static int check_usb_darts(struct atc_m1_hw*h){(void)h;return dart_ret;}
static void apple_boot_trace(const char*s){(void)s;}
static int dwc3_m1_diag_init_preserve_phy(struct dwc3*d){(void)d;core_calls++;return core_ret;}
static int dwc3_update_checked(struct atc_m1_hw *hw, u32 off,
                              u32 mask, u32 value)
{
 u32 old = readl(hw->xhci + off), next, observed;

 if (old == 0xffffffff || (value & ~mask))
  return -EIO;
 next = (old & ~mask) | value;
 writel(next, hw->xhci + off);
 observed = readl(hw->xhci + off);
 if (observed == 0xffffffff || observed != next)
  return -EIO;
 return 0;
}

static int prepare_dwc3_host(struct atc_m1_hw *hw)
{
 u32 id, params, ctl;
 int ret;

 if (hw->stage != ATC_CORE_READY)
  return -EPERM;
 ret = hw_verify_halted(hw);
 if (ret)
  return ret;
 id = readl(hw->xhci + 0xc120);
 params = readl(hw->xhci + 0xc140);
 ctl = readl(hw->xhci + 0xc110);
 /* The measured M1 DWC3.1 core is DRD; reject an unexpected core/reset. */
 if (id != 0x33313130 || params == 0xffffffff || (params & 3) != 2 ||
     ctl == 0xffffffff || (ctl & BIT(11)))
  return -ENODEV;
#define DWC3_UPDATE(off, mask, val) do { \
 ret = dwc3_update_checked(hw, off, mask, val); \
 if (ret) return ret; \
} while (0)
 if (hw->hostrun) {
#if CONFIG_IS_ENABLED(USB_XHCI_DWC3)
  ret = check_usb_darts(hw);
  if (ret) return ret;
  apple_boot_trace("dwc3-core-init-begin");
  ret = dwc3_m1_diag_init_preserve_phy((struct dwc3 *)(hw->xhci + DWC3_REG_OFFSET));
  apple_boot_trace("dwc3-core-init-return");
  printf("M1-DWC3 core-init preserve-phy ret=%d\n", ret);
  if (ret) return ret;
  ret = hw_verify_halted(hw);
  if (ret) return ret;
#else
  return -ENOSYS;
#endif
 }
 /* Apple CIO controls from dwc3_apple_setup_cio(), preserve upper timer bits. */
 DWC3_UPDATE(0xcd38, 0xffffffff, 0x0f800f80);
 DWC3_UPDATE(0xcd3c, 0xffffffff, 0x0fc00fc0);
 DWC3_UPDATE(0xcd40, 0x00ffffff, 0x00140a10);
 /* DRD role switching requires SUSPHY clear before selecting HOST. */
 DWC3_UPDATE(0xc2c0, BIT(17), 0);
 DWC3_UPDATE(0xc200, BIT(6), 0);
 DWC3_UPDATE(0xc110, 3 << 12, 1 << 12);
 /* Core USB2 LPM setup, followed by Apple-required SUSPHY before PIPE. */
 DWC3_UPDATE(0xc200, BIT(8) | BIT(6), BIT(8) | BIT(6));
 DWC3_UPDATE(0xc2c0, BIT(17), BIT(17));
#undef DWC3_UPDATE
 return hw_verify_halted(hw);
}
int main(void){struct atc_m1_hw h={mem,ATC_CORE_READY,0};unsigned cases=0;init();if(prepare_dwc3_host(&h)||writes!=8||halt_calls!=2)abort();unsigned total=reads;
if(mem[0xc110/4]!=0x30c11004||mem[0xc200/4]!=0x102540||mem[0xc2c0/4]!=0x1021102||mem[0xcd40/4]!=0x3c140a10||mem[0xcd38/4]!=0xf800f80||mem[0xcd3c/4]!=0xfc00fc0)abort();
cases++;
for(unsigned i=1;i<=total;i++){init();fail_read=i;if(prepare_dwc3_host(&h)>=0||reads!=(i<=3?3:i))abort();
cases++;}
init();h.stage=0;if(prepare_dwc3_host(&h)!=-EPERM||reads||writes)abort();h.stage=ATC_CORE_READY;cases++;
init();fail_halt=1;if(prepare_dwc3_host(&h)!=-EBUSY||reads||writes)abort();
cases++;
init();fail_halt=2;if(prepare_dwc3_host(&h)!=-EBUSY||writes!=8)abort();
cases++;
init();mem[0xc120/4]=0;if(prepare_dwc3_host(&h)!=-ENODEV||writes)abort();
cases++;
init();mem[0xc140/4]=1;if(prepare_dwc3_host(&h)!=-ENODEV||writes)abort();
cases++;
init();mem[0xc110/4]|=BIT(11);if(prepare_dwc3_host(&h)!=-ENODEV||writes)abort();
cases++;
/* Hostrun-only entry and failure ordering. */
 init(); h.hostrun=1; dart_ret=core_ret=core_calls=0;
 if(prepare_dwc3_host(&h)||core_calls!=1||writes!=8)abort();
 init();core_calls=0;dart_ret=-EPERM;
 if(prepare_dwc3_host(&h)!=-EPERM||core_calls||writes)abort();
 init();dart_ret=0;core_ret=-EIO;
 if(prepare_dwc3_host(&h)!=-EIO||writes)abort();
 init();core_ret=0;fail_halt=2;
 if(prepare_dwc3_host(&h)!=-EBUSY||writes)abort();
 cases+=4;
 printf("%u host setup cases, zero failures; %u read-fault positions\n",cases,total);return 0;}
