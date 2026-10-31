#!/usr/bin/env python3
"""Execute extracted Linux and U-Boot PHY code against the same fake MMIO.

No hardware access. This checks source-level writes, not analog behavior or
the Linux scheduler. The Linux call sequence is assembled explicitly below.
"""
from pathlib import Path
import re, subprocess, json, hashlib, difflib

import argparse
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--linux', type=Path, required=True)
parser.add_argument('--uboot', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
linux, uboot, out = args.linux.resolve(), args.uboot.resolve(), args.output.resolve()
out.mkdir(parents=True, exist_ok=True)
src = (linux/'drivers/phy/apple/atc.c').read_text()

def function(s, name):
    m = re.search(r'^(?:static )?(?:inline )?[^\n;{}]*\b'+name+r'\([^;{}]*\)\s*\{', s, re.M)
    if not m: raise ValueError(name)
    start=m.start(); pos=m.end(); depth=1
    while depth:
        depth += (s[pos]=='{')-(s[pos]=='}'); pos+=1
    return s[start:pos]+'\n'

pre = r'''
// SPDX-License-Identifier: GPL-2.0-only
// Extracted source: Asahi Linux contributors, original PHY author Sven Peter.
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <assert.h>
typedef uint32_t u32; typedef uint32_t __be32;
#define __iomem
#define BIT(n) (1U<<(n))
#define GENMASK(h,l) ((0xffffffffU >> (31-(h))) & (0xffffffffU << (l)))
#define FIELD_PREP(m,v) (((u32)(v)<<__builtin_ctz(m))&(m))
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
#define be32_to_cpu(v) __builtin_bswap32(v)
#define cpu_to_be32(v) __builtin_bswap32(v)
#define lockdep_assert_held(x) ((void)0)
#define dev_warn(...) ((void)0)
#define dev_err(...) ((void)0)
static u32 regs[5][0x4c000/4];
static int locate(void*p,unsigned*off){
 for(int r=0;r<5;r++)if((uintptr_t)p>=(uintptr_t)regs[r]&&(uintptr_t)p<(uintptr_t)(regs[r]+ARRAY_SIZE(regs[r]))){*off=(uintptr_t)p-(uintptr_t)regs[r];assert(!(*off%4));return r;}
 abort();
}
static u32 readl(void*p){unsigned off;int r=locate(p,&off);
 if(r==0&&off==0x20004)return regs[0][0x20000/4]&3;
 if(r==3&&off==0x14)return regs[3][0x10/4]&1;
 return *(u32*)p;
}
static void writel(u32 v,void*p){unsigned off;int r=locate(p,&off);*(u32*)p=v;printf("W %d %x %08x\n",r,off,v);}
static void udelay(unsigned us){printf("D %u\n",us);}
#define readl_poll_timeout(p,v,cond,delay,timeout) ({ (v)=readl(p); (cond)?0:-ETIMEDOUT; })
struct apple_tunable {size_t sz; struct {u32 offset,mask,value;} values[1024];};
'''
logical=src.replace('\\\n',' ')
defines='\n'.join(re.findall(r'^#define[^\n]*',logical,re.M))+'\n'
enums='\n'.join(re.findall(r'enum atcphy_\w+\s*\{[^}]*\};',src))
mode_struct=re.search(r'struct atcphy_mode_configuration\s*\{[^}]*\};',src)[0]
mode_table=src[src.index('static const struct {\n\tconst struct atcphy_mode_configuration'):src.index('static const struct {\n\tconst struct atcphy_mode_configuration')+1]
m=re.search(r'static const struct \{\s*const struct atcphy_mode_configuration[\s\S]*?\} atcphy_modes\[\] = \{[\s\S]*?^\};',src,re.M)
mode_table=m[0]
structs=r'''
struct atcphy_hw {int gen,aciophy_lane_mode,aciophy_crossbar;};
struct apple_atcphy {
 struct {void *core,*axi2af,*usb2phy,*pipehandler,*lpdptx;} regs;
 struct {struct apple_tunable *common[2],*axi2af,*lane_usb3[2],*lane_dp[2],*lane_usb4[2];} tunables;
 struct atcphy_hw *hw; bool swap_lanes; int lock; void *dev;
};
'''
names=['mask32','core_mask32','set32','core_set32','clear32','core_clear32',
 'atcphy_get_mode_config','atcphy_apply_tunables','atcphy_pipehandler_lock',
 'atcphy_pipehandler_unlock','atcphy_pipehandler_check','atcphy_pipehandler_set_mux',
 'atcphy_configure_pipehandler_usb4','atcphy_configure_pipehandler_dummy',
 'atcphy_setup_pipehandler','atcphy_configure_lanes','atcphy_disable_dp_aux',
 'atcphy_usb2_power_off','atcphy_power_off','atcphy_usb2_power_on','atcphy_power_on',
 'atcphy_configure_post_tunable_t8103','_atcphy_dwc3_reset_assert']
linux_code=defines+enums+mode_struct+mode_table+structs
linux_code+=function((linux/'drivers/soc/apple/tunable.c').read_text(),'apple_tunable_apply')
linux_code+='\n'.join(function(src,n) for n in names)
header=(uboot/'include/apple_atc_m1.h').read_text()
header=re.sub(r'^#include.*$','',header,flags=re.M)
code=re.sub(r'^#include.*$','',(uboot/'lib/apple_atc_m1.c').read_text(),flags=re.M)
data=(uboot/'test/dm/apple_atc_m1_data.h').read_text()
main=r'''
static int rd(void*c,enum atc_m1_region r,u32 o,u32*v){*v=readl((char*)regs[r]+o);return 0;}
static int wr(void*c,enum atc_m1_region r,u32 o,u32 v){writel(v,(char*)regs[r]+o);return 0;}
static void wait_us(void*c,unsigned us){udelay(us);}
static int halted(void*c){return 0;}
int main(int argc,char**argv){assert(argc==5);int flavor=atoi(argv[1]),mode=atoi(argv[2]),swap=atoi(argv[3]),pattern=atoi(argv[4]);
 for(int r=0;r<5;r++)for(unsigned i=0;i<ARRAY_SIZE(regs[r]);i++)regs[r][i]=pattern==0?0:pattern==1?0xffffffffU:(0xa53629b7U^(r*0x13579bU+i*0x10203U));
 // Initial lock is free in the hardware snapshots; power status follows control.
 regs[3][0x10/4]&=~1U;
 const __be32*arrays[]={calibration_0,calibration_1,calibration_2,calibration_3,calibration_4};
 size_t sizes[]={sizeof(calibration_0),sizeof(calibration_1),sizeof(calibration_2),sizeof(calibration_3),sizeof(calibration_4)};
 if(!flavor){
  struct apple_tunable tables[5]={0};for(int g=0;g<5;g++){tables[g].sz=sizes[g]/12;for(unsigned i=0;i<tables[g].sz;i++){tables[g].values[i].offset=be32_to_cpu(arrays[g][i*3]);tables[g].values[i].mask=be32_to_cpu(arrays[g][i*3+1]);tables[g].values[i].value=be32_to_cpu(arrays[g][i*3+2]);}}
  struct atcphy_hw hw={ATCPHY_GENERATION_T8103,0x48,0x4c};
  struct apple_atcphy a={.regs={regs[0],regs[1],regs[2],regs[3],regs[4]},.hw=&hw,.swap_lanes=swap};
  a.tunables.common[0]=&tables[0];a.tunables.axi2af=&tables[1];a.tunables.common[1]=&tables[2];a.tunables.lane_usb4[0]=&tables[3];a.tunables.lane_usb4[1]=&tables[4];
  int m=mode?APPLE_ATCPHY_MODE_TBT:APPLE_ATCPHY_MODE_USB4;
  _atcphy_dwc3_reset_assert(&a);atcphy_usb2_power_off(&a);assert(!atcphy_power_off(&a));atcphy_setup_pipehandler(&a);
  assert(!atcphy_power_on(&a));atcphy_apply_tunables(&a,m);atcphy_configure_post_tunable_t8103(&a,m);
  core_set32(&a,CIO3PLL_CLK_CTRL,CIO3PLL_CLK_PCLK_EN);core_set32(&a,CIO3PLL_CLK_CTRL,CIO3PLL_CLK_REFCLK_EN);
  atcphy_configure_lanes(&a,m);core_set32(&a,ATCPHY_POWER_CTRL,ATCPHY_POWER_PHY_RESET_N);
  clear32(a.regs.pipehandler+PIPEHANDLER_AON_GEN,PIPEHANDLER_AON_GEN_DWC3_FORCE_CLAMP_EN);set32(a.regs.pipehandler+PIPEHANDLER_AON_GEN,PIPEHANDLER_AON_GEN_DWC3_RESET_N);
  assert(!(mode?atcphy_configure_pipehandler_dummy(&a):atcphy_configure_pipehandler_usb4(&a)));
 }else{
  struct atc_m1_config c={.mode=mode?ATC_TBT:ATC_USB4,.swapped=swap,.retain_dwc3=true,.size={0x4c000,0x4000,0x4000,0x4000,0x8000}};
  for(int g=0;g<5;g++)c.tunable[g]=(struct atc_m1_tunable){arrays[g],sizes[g]};
  struct atc_m1_io io={rd,wr,wait_us,halted};enum atc_m1_stage stage;assert(!atc_m1_start(&c,&io,NULL,true,&stage));
 }
 return 0;
}
'''
generated=pre+linux_code+header+code+data+main
(out/'phy-source-comparison.c').write_text(generated)
subprocess.run(['cc','-std=gnu11','-O1','-g','-fsanitize=address,undefined','-fno-pie','-no-pie',str(out/'phy-source-comparison.c'),'-o',str(out/'phy-source-comparison')],check=True)
results=[]
for mode in range(2):
 for swap in range(2):
  for pattern in range(3):
   traces=[]
   for flavor in range(2):
    r=subprocess.run([str(out/'phy-source-comparison'),str(flavor),str(mode),str(swap),str(pattern)],capture_output=True,text=True,check=True)
    traces.append(r.stdout.splitlines())
   changes=[]
   for tag,i,j,k,l in difflib.SequenceMatcher(a=traces[0],b=traces[1],autojunk=False).get_opcodes():
    if tag!='equal':changes.append({'kind':tag,'linux':traces[0][i:j],'uboot':traces[1][k:l],'linux_index':i,'uboot_index':k})
   results.append(dict(mode='TBT' if mode else 'USB4',swapped=bool(swap),pattern=pattern,linux_operations=len(traces[0]),uboot_operations=len(traces[1]),differences=changes))
report={'scope':'Extracted Linux functions vs extracted candidate U-Boot function; fake MMIO, no hardware or concurrency proof','cases':results,'sources_sha256':{str(p.relative_to(linux)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [linux/'drivers/phy/apple/atc.c',linux/'drivers/soc/apple/tunable.c']}}
(out/'phy-source-comparison.json').write_text(json.dumps(report,indent=2)+'\n')
for r in results:print(r)
