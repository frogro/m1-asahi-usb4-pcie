#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <errno.h>
#include <string.h>
#include <assert.h>
#define debug(...) ((void)0)
#define HCS_SLOTS_MASK 255
#define HCS_MAX_PORTS(x) (((x)>>24)&255)
#define HCS_INDICATOR(x) 0
#define HCC_PPC(x) 0
#define HC_VERSION(x) ((x)>>16)
#define get_unaligned(p) (*(p))
#define put_unaligned(v,p) (*(p)=(v))
struct hub { unsigned bNbrPorts;uint16_t wHubCharacteristics; };
static struct {struct hub hub;} descriptor;
struct xhci_hccr {uint32_t cr_hcsparams1,cr_hccparams,cr_capbase;};
struct xhci_hcor {uint32_t or_config;};
struct ir {uint32_t irq_control,irq_pending;};
struct xhci_ctrl {struct xhci_hccr*hccr;struct xhci_hcor*hcor;struct hub hub_desc;struct ir*ir_set;bool m1_diag,m1_dma_failed;unsigned m1_dma_maps,hci_version;};
static int mem_error,start_error,starts,resets;static bool map_failed;static unsigned maps;static struct ir ir;
static uint32_t xhci_readl(uint32_t*p){return *p;}
static void xhci_writel(uint32_t*p,uint32_t v){*p=v;}
static int xhci_mem_init(struct xhci_ctrl*c,struct xhci_hccr*a,struct xhci_hcor*b){(void)a;(void)b;c->ir_set=&ir;c->m1_dma_maps=maps;c->m1_dma_failed=map_failed;return mem_error;}
static int xhci_start(struct xhci_hcor*h){(void)h;starts++;return start_error;}
static int xhci_reset(struct xhci_hcor*h){(void)h;resets++;return 0;}
static int xhci_lowlevel_init(struct xhci_ctrl *ctrl)
{
	struct xhci_hccr *hccr;
	struct xhci_hcor *hcor;
	uint32_t val;
	uint32_t val2;
	uint32_t reg;

	hccr = ctrl->hccr;
	hcor = ctrl->hcor;
	/*
	 * Program the Number of Device Slots Enabled field in the CONFIG
	 * register with the max value of slots the HC can handle.
	 */
	val = (xhci_readl(&hccr->cr_hcsparams1) & HCS_SLOTS_MASK);
	val2 = xhci_readl(&hcor->or_config);
	val |= (val2 & ~HCS_SLOTS_MASK);
	xhci_writel(&hcor->or_config, val);

	/* initializing xhci data structures */
	if (xhci_mem_init(ctrl, hccr, hcor) < 0)
		return -ENOMEM;
	ctrl->hub_desc = descriptor.hub;

	reg = xhci_readl(&hccr->cr_hcsparams1);
	ctrl->hub_desc.bNbrPorts = HCS_MAX_PORTS(reg);
	debug("Register %x NbrPorts %d\n", reg, ctrl->hub_desc.bNbrPorts);

	/* Port Indicators */
	reg = xhci_readl(&hccr->cr_hccparams);
	if (HCS_INDICATOR(reg))
		put_unaligned(get_unaligned(&ctrl->hub_desc.wHubCharacteristics)
				| 0x80, &ctrl->hub_desc.wHubCharacteristics);

	/* Port Power Control */
	if (HCC_PPC(reg))
		put_unaligned(get_unaligned(&ctrl->hub_desc.wHubCharacteristics)
				| 0x01, &ctrl->hub_desc.wHubCharacteristics);

	/* No RUN write after a failed diagnostic DMA mapping. */
	if (ctrl->m1_diag && (ctrl->m1_dma_failed || ctrl->m1_dma_maps < 4))
		return -EFAULT;

	if (xhci_start(hcor)) {
		xhci_reset(hcor);
		return -ENODEV;
	}

	/* Zero'ing IRQ control register and IRQ pending register */
	xhci_writel(&ctrl->ir_set->irq_control, 0x0);
	xhci_writel(&ctrl->ir_set->irq_pending, 0x0);

	reg = HC_VERSION(xhci_readl(&hccr->cr_capbase));
	printf("USB XHCI %x.%02x\n", reg >> 8, reg & 0xff);
	ctrl->hci_version = reg;

	return 0;
}

int main(void){
 struct xhci_hccr cap={0x02000020,0,0x1000040};struct xhci_hcor op={0};int cases=0;
 for(int diag=0;diag<2;diag++)for(int fault=0;fault<5;fault++){
  struct xhci_ctrl c={.hccr=&cap,.hcor=&op,.m1_diag=diag};
  starts=resets=0;mem_error=fault==1?-ENOMEM:0;map_failed=fault==2;maps=fault==3?3:4;start_error=fault==4?-ETIMEDOUT:0;
  int ret=xhci_lowlevel_init(&c);
  int expected=mem_error?-ENOMEM:diag&&(map_failed||maps<4)?-EFAULT:start_error?-ENODEV:0;
  assert(ret==expected);
  assert(starts==(!mem_error&&!(diag&&(map_failed||maps<4))));
  assert(resets==(starts&&start_error));cases++;
 }
 printf("%d actual lowlevel-init DMA/RUN guard cases passed\n",cases);
}
