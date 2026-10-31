// SPDX-License-Identifier: GPL-2.0+
// Extracted existing U-Boot DWC3 implementation; original authors retained in source.
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
typedef uint32_t u32;
#define debug(...) ((void)0)
struct dwc3 {u32 g_snpsid,g_hwparams1,g_ctl,g_usb2phycfg,g_usb3pipectl[1];};
struct event {unsigned kind,offset;u32 value;};
static struct dwc3 regs;static struct event events[64];static unsigned count,writes,delays;
static u32 readl(u32*p){return *p;}
static void writel(u32 v,u32*p){assert(count<64);events[count++]=(struct event){1,(unsigned)((uintptr_t)p-(uintptr_t)&regs),v};*p=v;writes++;}
static void setbits_le32(u32*p,u32 m){writel(readl(p)|m,p);}
static void clrbits_le32(u32*p,u32 m){writel(readl(p)&~m,p);}
static void mdelay(unsigned ms){events[count++]=(struct event){2,0,ms};delays+=ms;}
#define DWC3_GSNPSID_MASK			0xffff0000
#define DWC3_REVISION_MASK			0xffff
#define DWC3_GCTL_U2RSTECN			(1 << 16)
#define DWC3_GCTL_SCALEDOWN(n)			((n) << 4)
#define DWC3_GCTL_SCALEDOWN_MASK		DWC3_GCTL_SCALEDOWN(3)
#define DWC3_GCTL_DISSCRAMBLE			(1 << 3)
#define DWC3_GCTL_DSBLCLKGTNG			(1 << 0)
#define DWC3_GHWPARAMS1_EN_PWROPT(n)		(((n) & (3 << 24)) >> 24)
#define DWC3_GHWPARAMS1_EN_PWROPT_CLK		1
#define DWC3_GCTL_CORESOFTRESET			(1 << 11)
#define DWC3_GUSB3PIPECTL_PHYSOFTRST		(1 << 31)
#define DWC3_GUSB2PHYCFG_PHYSOFTRST		(1 << 31)
static void dwc3_phy_reset(struct dwc3 *dwc3_reg)
{
	/* Assert USB3 PHY reset */
	setbits_le32(&dwc3_reg->g_usb3pipectl[0], DWC3_GUSB3PIPECTL_PHYSOFTRST);

	/* Assert USB2 PHY reset */
	setbits_le32(&dwc3_reg->g_usb2phycfg, DWC3_GUSB2PHYCFG_PHYSOFTRST);

	mdelay(100);

	/* Clear USB3 PHY reset */
	clrbits_le32(&dwc3_reg->g_usb3pipectl[0], DWC3_GUSB3PIPECTL_PHYSOFTRST);

	/* Clear USB2 PHY reset */
	clrbits_le32(&dwc3_reg->g_usb2phycfg, DWC3_GUSB2PHYCFG_PHYSOFTRST);
}
void dwc3_core_soft_reset(struct dwc3 *dwc3_reg)
{
	/* Before Resetting PHY, put Core in Reset */
	setbits_le32(&dwc3_reg->g_ctl, DWC3_GCTL_CORESOFTRESET);

	/* reset USB3 phy - if required */
	dwc3_phy_reset(dwc3_reg);

	mdelay(100);

	/* After PHYs are stable we can take Core out of reset state */
	clrbits_le32(&dwc3_reg->g_ctl, DWC3_GCTL_CORESOFTRESET);
}
int old_dwc3_core_init(struct dwc3 *dwc3_reg)
{
	u32 reg;
	u32 revision;
	unsigned int dwc3_hwparams1;

	revision = readl(&dwc3_reg->g_snpsid);
	/* This should read as U3 followed by revision number */
	if ((revision & DWC3_GSNPSID_MASK) != 0x55330000 &&
	    (revision & DWC3_GSNPSID_MASK) != 0x33310000) {
		puts("this is not a DesignWare USB3 DRD Core\n");
		return -1;
	}

	dwc3_core_soft_reset(dwc3_reg);

	dwc3_hwparams1 = readl(&dwc3_reg->g_hwparams1);

	reg = readl(&dwc3_reg->g_ctl);
	reg &= ~DWC3_GCTL_SCALEDOWN_MASK;
	reg &= ~DWC3_GCTL_DISSCRAMBLE;
	switch (DWC3_GHWPARAMS1_EN_PWROPT(dwc3_hwparams1)) {
	case DWC3_GHWPARAMS1_EN_PWROPT_CLK:
		reg &= ~DWC3_GCTL_DSBLCLKGTNG;
		break;
	default:
		debug("No power optimization available\n");
	}

	/*
	 * WORKAROUND: DWC3 revisions <1.90a have a bug
	 * where the device can fail to connect at SuperSpeed
	 * and falls back to high-speed mode which causes
	 * the device to enter a Connect/Disconnect loop
	 */
	if ((revision & DWC3_REVISION_MASK) < 0x190a)
		reg |= DWC3_GCTL_U2RSTECN;

	writel(reg, &dwc3_reg->g_ctl);

	return 0;
}
static int dwc3_core_init_common(struct dwc3 *dwc3_reg, bool reset_phy)
{
	u32 reg;
	u32 revision;
	unsigned int dwc3_hwparams1;

	revision = readl(&dwc3_reg->g_snpsid);
	/* This should read as U3 followed by revision number */
	if ((revision & DWC3_GSNPSID_MASK) != 0x55330000 &&
	    (revision & DWC3_GSNPSID_MASK) != 0x33310000) {
		puts("this is not a DesignWare USB3 DRD Core\n");
		return -1;
	}

	if (reset_phy)
		dwc3_core_soft_reset(dwc3_reg);

	dwc3_hwparams1 = readl(&dwc3_reg->g_hwparams1);

	reg = readl(&dwc3_reg->g_ctl);
	reg &= ~DWC3_GCTL_SCALEDOWN_MASK;
	reg &= ~DWC3_GCTL_DISSCRAMBLE;
	switch (DWC3_GHWPARAMS1_EN_PWROPT(dwc3_hwparams1)) {
	case DWC3_GHWPARAMS1_EN_PWROPT_CLK:
		reg &= ~DWC3_GCTL_DSBLCLKGTNG;
		break;
	default:
		debug("No power optimization available\n");
	}

	/*
	 * WORKAROUND: DWC3 revisions <1.90a have a bug
	 * where the device can fail to connect at SuperSpeed
	 * and falls back to high-speed mode which causes
	 * the device to enter a Connect/Disconnect loop
	 */
	if ((revision & DWC3_REVISION_MASK) < 0x190a)
		reg |= DWC3_GCTL_U2RSTECN;

	writel(reg, &dwc3_reg->g_ctl);

	return 0;
}
int dwc3_core_init(struct dwc3 *dwc3_reg)
{
	return dwc3_core_init_common(dwc3_reg, true);
}
int dwc3_m1_diag_init_preserve_phy(struct dwc3 *dwc3_reg)
{
	return dwc3_core_init_common(dwc3_reg, false);
}
int main(void){
 const u32 ids[]={0x33313130,0x5533180a,0x5533190a,0,0xffffffff};
 const u32 patterns[]={0,0xffffffff,0xa53629b7};
 unsigned cases=0;
 for(unsigned id=0;id<5;id++)for(unsigned p=0;p<4;p++)for(unsigned v=0;v<3;v++){
  struct dwc3 initial={ids[id],p<<24,patterns[v]&~DWC3_GCTL_CORESOFTRESET,0x102540,{0x1021102}};
  regs=initial;count=writes=delays=0;int a=old_dwc3_core_init(&regs);struct dwc3 expected=regs;unsigned n=count;struct event ev[64];memcpy(ev,events,sizeof ev);
  regs=initial;count=writes=delays=0;int b=dwc3_core_init(&regs);
  assert(a==b&&!memcmp(&regs,&expected,sizeof regs)&&n==count&&!memcmp(ev,events,count*sizeof(*ev)));
  regs=initial;count=writes=delays=0;int c=dwc3_m1_diag_init_preserve_phy(&regs);
  assert(a==c&&regs.g_ctl==expected.g_ctl&&regs.g_usb2phycfg==initial.g_usb2phycfg&&regs.g_usb3pipectl[0]==initial.g_usb3pipectl[0]);
  assert(delays==0&&writes==(id<3?1U:0U));cases++;
 }
 printf("%u extracted DWC3 scenarios: legacy write/delay parity and reset-free identical GCTL passed\n",cases);
}
