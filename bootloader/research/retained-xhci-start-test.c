#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <errno.h>
#include <assert.h>
typedef uint32_t u32; typedef uint64_t dma_addr_t;
#define HC_LENGTH(x) ((x)&255)
#define HCS_SLOTS_MASK 255
#define HCS_MAX_PORTS(x) (((x)>>24)&255)
#define HCS_MAX_SCRATCHPAD(x) ((((x)>>27)&31) | (((x)>>16)&0x3e0))
#define CMD_RUN 1
#define STS_HALT 1
#define XHCI_ALIGNMENT 64
#define ARCH_DMA_MINALIGN 64
#define max(a,b) ((a)>(b)?(a):(b))
#define HCC_PPC(x) ((x)&8)
#define PORT_POWER (1U<<9)
#define XHCI_PORT_RO ((1 << 0) | (1 << 3) | (0xf << 10) | (1 << 30))
#define XHCI_PORT_RWS ((0xf << 5) | (1 << 9) | (0x3 << 14) | (0x7 << 25))
struct udevice { int unused; };
struct xhci_hccr { u32 cr_capbase,cr_hcsparams1,cr_hcsparams2,cr_dboff,cr_rtsoff,cr_hccparams; };
struct port { u32 or_portsc; };
struct xhci_hcor { u32 or_pagesize,or_usbcmd,or_usbsts; struct port portregs[16]; };
struct xhci_ctrl { struct udevice *dev; struct xhci_hccr *hccr; struct xhci_hcor *hcor; bool m1_diag,m1_dma_failed; unsigned m1_dma_maps; };
static bool m1_diag_attempted;
static int reads,writes,allocs,resets,inits,waits,reset_error,init_error,wait_error,alloc_error;
static u32 xhci_readl(u32 *p) { reads++; return *p; }
static void xhci_writel(u32 *p,u32 v) { writes++; *p=v; }
static void *memalign(size_t a,size_t n) { allocs++;if(alloc_error)return NULL;return aligned_alloc(a,(n+a-1)&~(a-1)); }
static int xhci_reset(struct xhci_hcor *h) { (void)h;resets++;return reset_error; }
static int xhci_lowlevel_init(struct xhci_ctrl *c) { inits++;assert(c->m1_diag);c->m1_dma_maps=4;return init_error; }
static int handshake(u32 *p,u32 mask,u32 value,unsigned timeout) { (void)p;assert(mask==STS_HALT&&value==STS_HALT&&timeout==100000);waits++;return wait_error; }

static inline bool xhci_m1_dma_valid(dma_addr_t mapped, uintptr_t addr, size_t size)
{
 return addr && size && size <= ~(dma_addr_t)0 - addr && mapped == addr;
}
static bool xhci_m1_caps_valid(u32 cap, u32 slots_ports, u32 scratch,
                              u32 dboff, u32 rtsoff, u32 pages)
{
 unsigned int nsp = HCS_MAX_SCRATCHPAD(scratch);
 unsigned int nports = HCS_MAX_PORTS(slots_ports);
 return cap >= 0x20 && cap <= 0x100 && !(cap & 3) &&
        (slots_ports & HCS_SLOTS_MASK) && nports && nports <= 16 &&
        nsp <= 64 && (pages & 0xffff) &&
        dboff >= 0x1000 && dboff <= 0xa000 && !(dboff & 3) &&
        rtsoff >= 0x1000 && rtsoff <= 0xa000 && !(rtsoff & 31);
}
static u32 xhci_port_state_to_neutral(u32 state)
{
	/* Save read-only status and port state */
	return (state & XHCI_PORT_RO) | (state & XHCI_PORT_RWS);
}
static int xhci_m1_diag_port_power(struct xhci_ctrl *ctrl)
{
 unsigned int i, ports = HCS_MAX_PORTS(xhci_readl(&ctrl->hccr->cr_hcsparams1));
 bool ppc = HCC_PPC(xhci_readl(&ctrl->hccr->cr_hccparams));
 u32 state;
 if (!ports || ports > 16) return -EPROTO;
 for (i = 0; i < ports; i++) {
  state = xhci_readl(&ctrl->hcor->portregs[i].or_portsc);
  if (state == ~0U) return -ENODEV;
  if (ppc && !(state & PORT_POWER)) {
   /* Same neutral RWS mask as USB_PORT_FEAT_POWER; no reset/W1C writes. */
   xhci_writel(&ctrl->hcor->portregs[i].or_portsc,
               xhci_port_state_to_neutral(state) | PORT_POWER);
   state = xhci_readl(&ctrl->hcor->portregs[i].or_portsc);
   if (state == ~0U || !(state & PORT_POWER)) return -EIO;
  }
  printf("M1-XHCI port%u power-control=%u status=%#x\n", i + 1, ppc, state);
 }
 return 0;
}
int xhci_m1_diag_start(struct udevice *dev, struct xhci_hccr *hccr,
                     struct xhci_hcor *hcor, struct xhci_ctrl **retained)
{
 struct xhci_ctrl *ctrl;
 u32 cap;
 int ret;
 if (!dev || !hccr || !hcor || !retained || *retained || m1_diag_attempted)
  return -EPERM;
 cap = HC_LENGTH(xhci_readl(&hccr->cr_capbase));
 if (!xhci_m1_caps_valid(cap, xhci_readl(&hccr->cr_hcsparams1),
                         xhci_readl(&hccr->cr_hcsparams2),
                         xhci_readl(&hccr->cr_dboff),
                         xhci_readl(&hccr->cr_rtsoff),
                         xhci_readl(&hcor->or_pagesize)))
  return -EPROTO;
 if (xhci_readl(&hcor->or_usbcmd) & CMD_RUN ||
     !(xhci_readl(&hcor->or_usbsts) & STS_HALT))
  return -EBUSY;
 ctrl = memalign(max(XHCI_ALIGNMENT, ARCH_DMA_MINALIGN), sizeof(*ctrl));
 if (!ctrl) return -ENOMEM;
 memset(ctrl, 0, sizeof(*ctrl));
 m1_diag_attempted = true;
 *retained = ctrl;
 ctrl->dev = dev;
 ctrl->hccr = hccr;
 ctrl->hcor = hcor;
 ctrl->m1_diag = true;
 ret = xhci_reset(hcor);
 if (!ret) ret = xhci_lowlevel_init(ctrl);
 if (!ret) ret = xhci_m1_diag_port_power(ctrl);
 printf("M1-XHCI start ret=%d maps=%u dma_failed=%u command=%#x status=%#x\n",
        ret, ctrl->m1_dma_maps, ctrl->m1_dma_failed,
        xhci_readl(&hcor->or_usbcmd), xhci_readl(&hcor->or_usbsts));
 puts("M1-XHCI buffers retained until full reset; no USB enumeration\n");
 return ret;
}
int xhci_m1_diag_stop(struct xhci_ctrl *ctrl)
{
 u32 cmd;
 if (!ctrl || !ctrl->m1_diag || !ctrl->hcor) return -EINVAL;
 cmd = xhci_readl(&ctrl->hcor->or_usbcmd);
 if (cmd == ~0U) return -ENODEV;
 xhci_writel(&ctrl->hcor->or_usbcmd, cmd & ~CMD_RUN);
 /* Halt only; never free buffers, reset PHY or clear DART ownership here. */
 return handshake(&ctrl->hcor->or_usbsts, STS_HALT, STS_HALT, 100000);
}
static int cases;
static struct udevice dev;
static struct xhci_hccr hc;
static struct xhci_hcor op;
static void fresh(void) { hc=(struct xhci_hccr){0x40,0x02000020,0,0x2000,0x3000,0};op=(struct xhci_hcor){.or_pagesize=1,.or_usbsts=1};reads=writes=allocs=resets=inits=waits=reset_error=init_error=wait_error=alloc_error=0;m1_diag_attempted=false; }
static void start_case(int kind,int expected) {
 struct xhci_ctrl *retained=NULL;fresh();
 switch(kind) {
 case 1:hc.cr_capbase=0;break;case 2:hc.cr_capbase=0x41;break;
 case 3:hc.cr_hcsparams1=0;break;case 4:hc.cr_hcsparams1=0xff000001;break;
 case 5:hc.cr_hcsparams2=~0U;break;case 6:hc.cr_dboff=0;break;
 case 7:hc.cr_dboff=0xb000;break;case 8:hc.cr_dboff=0x2001;break;
 case 9:hc.cr_rtsoff=0;break;case 10:hc.cr_rtsoff=0xb000;break;
 case 11:hc.cr_rtsoff=0x2001;break;case 12:op.or_pagesize=0;break;
 case 13:op.or_usbcmd=1;break;case 14:op.or_usbsts=0;break;
 case 15:alloc_error=1;break;case 16:reset_error=-ETIMEDOUT;break;
 case 17:init_error=-EFAULT;break;case 18:init_error=-ENOMEM;break;
 }
 assert(xhci_m1_diag_start(&dev,&hc,&op,&retained)==expected);
 if (kind>=1&&kind<=14)assert(!retained&&!allocs&&!resets&&!inits&&!writes);
 if (kind==15)assert(!retained&&!resets&&!inits);
 if(kind==0||kind>=16) {
  assert(retained&&retained->m1_diag&&retained->dev==&dev&&m1_diag_attempted);
  assert(resets==1&&inits==(kind!=16));
  int oldreads=reads;
  assert(xhci_m1_diag_start(&dev,&hc,&op,&retained)==-EPERM);
  assert(reads==oldreads); /* no second hardware attempt */
  op.or_usbcmd=0x405;assert(!xhci_m1_diag_stop(retained));assert(op.or_usbcmd==0x404&&writes==1&&waits==1);
  wait_error=-ETIMEDOUT;assert(xhci_m1_diag_stop(retained)==-ETIMEDOUT);
  op.or_usbcmd=~0U;int oldwrites=writes;assert(xhci_m1_diag_stop(retained)==-ENODEV&&oldwrites==writes);
  free(retained); /* test only: production never releases this context */
 }
 cases++;
}
int main(void) {
 for(int i=0;i<=18;i++) start_case(i,i==0?0:i<=12?-EPROTO:i<=14?-EBUSY:i==15?-ENOMEM:i==16?-ETIMEDOUT:i==17?-EFAULT:-ENOMEM);
 fresh();struct xhci_ctrl *ptr=NULL;
 assert(xhci_m1_diag_start(NULL,&hc,&op,&ptr)==-EPERM);
 assert(xhci_m1_diag_start(&dev,NULL,&op,&ptr)==-EPERM);
 assert(xhci_m1_diag_start(&dev,&hc,NULL,&ptr)==-EPERM);
 assert(xhci_m1_diag_start(&dev,&hc,&op,NULL)==-EPERM);
 assert(!reads&&!writes);cases+=4;
 assert(!xhci_m1_dma_valid(0,0,1));assert(!xhci_m1_dma_valid(4,4,0));
 assert(!xhci_m1_dma_valid(0,0x800040000ULL,64));
 assert(!xhci_m1_dma_valid(0x4000,0x800040000ULL,64));
 assert(!xhci_m1_dma_valid(UINT64_MAX-1,UINT64_MAX-1,4));
 assert(xhci_m1_dma_valid(0x800040000ULL,0x800040000ULL,64));cases+=6;
 assert(xhci_m1_diag_stop(NULL)==-EINVAL);cases++;
 /* Root-port power must preserve RWS and avoid W1C/reset writes. */
 fresh();hc.cr_hccparams=8;struct xhci_ctrl pc={.hccr=&hc,.hcor=&op};
 op.portregs[0].or_portsc=(1U<<17)|(1U<<4)|(1U<<5);op.portregs[1].or_portsc=PORT_POWER;
 assert(!xhci_m1_diag_port_power(&pc));assert(writes==1);
 assert(op.portregs[0].or_portsc==(PORT_POWER|(1U<<5)));cases++;
 fresh();pc.hccr=&hc;pc.hcor=&op;op.portregs[0].or_portsc=~0U;
 assert(xhci_m1_diag_port_power(&pc)==-ENODEV&&!writes);cases++;
 fresh();hc.cr_hcsparams1=0;
 assert(xhci_m1_diag_port_power(&pc)==-EPROTO&&!writes);cases++;
 printf("%d extracted start/stop/capability/DMA/port cases passed\n",cases);
}
