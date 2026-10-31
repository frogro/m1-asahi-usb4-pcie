#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <errno.h>
#include <string.h>
#include <assert.h>
typedef uint32_t u32; typedef uint64_t u64;
#define BIT(n) (1U<<(n))
#define UCLASS_IOMMU 1
struct udevice { struct udevice *iommu; int id; };
struct atc_m1_hw { struct udevice *usb; };
struct ofnode_phandle_args { int node; unsigned args_count; unsigned args[1]; };
static struct udevice darts[2]={{.id=0},{.id=1}},usb;
static u32 regs[2][0x4000/4];
static int kind,target,cur,reads,maps,powers;
static int dev_count_phandle_with_args(struct udevice*d,const char*a,const char*b,int c){(void)d;(void)a;(void)b;(void)c;return kind==1?1:2;}
static int dev_read_phandle_with_args(struct udevice*d,const char*a,const char*b,int c,int i,struct ofnode_phandle_args*p){(void)d;(void)a;(void)b;(void)c;cur=i;p->node=i;p->args_count=(kind==3&&i==target)?0:1;p->args[0]=(kind==4&&i==target)?9:i;return(kind==2&&i==target)?-EIO:0;}
static u64 ofnode_get_addr(int n){return(kind==5&&cur==target)?0:(n?0x502f80000ULL:0x502f00000ULL);}
static int uclass_find_device_by_ofnode(int u,int n,struct udevice**d){assert(u==1);*d=&darts[n];return(kind==6&&cur==target)?-ENODEV:0;}
static bool device_active(struct udevice*d){(void)d;return !(kind==7&&cur==target);}
static int dev_power_domain_on(struct udevice*d){(void)d;powers++;return(kind==8&&cur==target)?-EIO:0;}
static void *map_sysmem(u64 a,unsigned z){assert(z==0x4000);assert(a==0x502f00000ULL||a==0x502f80000ULL);maps++;return regs[cur];}
static u32 readl(void*p){reads++;return *(u32*)p;}
static int check_usb_darts(struct atc_m1_hw *hw)
{
 static const u64 bases[] = { 0x502f00000ULL, 0x502f80000ULL };
 struct ofnode_phandle_args args;
 struct udevice *dart;
 void *regs;
 u32 control, error;
 int i, ret;
 if (dev_count_phandle_with_args(hw->usb, "iommus", "#iommu-cells", 0) != 2)
  return -EINVAL;
 for (i = 0; i < 2; i++) {
  ret = dev_read_phandle_with_args(hw->usb, "iommus", "#iommu-cells", 0, i, &args);
  if (ret) return ret;
  if (args.args_count != 1 || args.args[0] != (unsigned int)i ||
      ofnode_get_addr(args.node) != bases[i]) return -EINVAL;
  ret = uclass_find_device_by_ofnode(UCLASS_IOMMU, args.node, &dart);
  if (ret || !device_active(dart)) return -ENODEV;
  ret = dev_power_domain_on(dart);
  if (ret) return ret;
  regs = map_sysmem(bases[i], 0x4000);
  control = readl(regs + 0x100 + 4 * i);
  error = readl(regs + 0x40);
  printf("M1-XHCI DART%u sid=%u tcr=%#x error=%#x\n", i, i, control, error);
  if (!(readl(regs + 4) & BIT(0)) || control != (BIT(8) | BIT(12)) ||
      (error & BIT(31))) return -EPERM;
  if (i == 1 && hw->usb->iommu != dart) return -EINVAL;
 }
 return 0;
}

int main(void){
 int cases=0;
 for(target=0;target<2;target++)for(kind=0;kind<=12;kind++){
  memset(regs,0,sizeof(regs));for(int i=0;i<2;i++){regs[i][1]=1;regs[i][(0x100+4*i)/4]=0x1100;}
  if(kind==9)regs[target][1]=0;
  if(kind==10)regs[target][(0x100+4*target)/4]=0x80;
  if(kind==11)regs[target][0x40/4]=BIT(31);
  usb.iommu=kind==12?&darts[0]:&darts[1];
  reads=maps=powers=0;struct atc_m1_hw hw={&usb};
  int ret=check_usb_darts(&hw);assert((ret==0)==(kind==0));
  if(kind==1)assert(!reads&&!maps&&!powers);
  if(kind>=2&&kind<=8)assert(maps==target&&reads==3*target);
  if(kind==0)assert(maps==2&&reads==6&&powers==2);
  cases++;
 }
 printf("%d extracted dual-DART preflight cases passed\n",cases);
}
