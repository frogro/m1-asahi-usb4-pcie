from pathlib import Path
import subprocess,json
w=Path(__file__).resolve().parent;p=w/'endpoint-tests';p.mkdir(exist_ok=True);s=(w/'source/cmd/apple_nhi_m1_ring.c').read_text();(p/'actual.inc').write_text(s[s.index('static int diagnostic_usb4_endpoint_scan'):s.index('static int diagnostic_usb4_paths')]);c=r'''#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <errno.h>
#include <assert.h>
#include <string.h>
typedef uint32_t u32;
#define USB4_CFG_READ 1
#define USB4_CFG_WRITE 2
'''+(w/'usb4-snapshot.h').read_text()+r'''
struct diagnostic_ring{struct apple_usb4_snapshot usb4_snapshot;};
static unsigned calls,fail,afterwrite,link,scan,nvme;static u32 regs[2];
static int diagnostic_xfer(struct diagnostic_ring*r,unsigned port,unsigned space,unsigned offset,unsigned words,u32*d,unsigned type,unsigned route){assert(route<2&&port==3&&space==1&&offset==9&&words==1);calls++;if(calls==fail&&!afterwrite)return -EIO;if(type==USB4_CFG_READ)*d=regs[route];else{assert(type==USB4_CFG_WRITE);if(*d>>31){if(route==0)assert(regs[1]>>31);}else{if(route==1&&!fail)assert(!(regs[0]>>31));}regs[route]=*d;}if(calls==fail)return -EIO;return 0;}
static int apple_pciec_m1_start_link(void){assert(regs[0]>>31&&regs[1]>>31);calls++;link++;return calls==fail?-EIO:0;}
static int apple_pciec_m1_scan(void){assert(link&&regs[0]>>31&&regs[1]>>31);calls++;scan++;return calls==fail?-EIO:0;}
static int apple_pciec_m1_nvme_read(void){assert(scan&&regs[0]>>31&&regs[1]>>31);calls++;nvme++;return calls==fail?-EIO:0;}
#include "actual.inc"
static void init(struct diagnostic_ring*r){memset(r,0,sizeof *r);r->usb4_snapshot.port[0]=r->usb4_snapshot.port[3]=3;r->usb4_snapshot.cap[0]=r->usb4_snapshot.cap[3]=9;regs[0]=regs[1]=0xe0400;calls=fail=afterwrite=link=scan=nvme=0;}
int main(void){struct diagnostic_ring r;unsigned n=0;init(&r);assert(!diagnostic_usb4_endpoint_scan(&r,15)&&scan==1&&nvme==1&&regs[0]==0xe0400&&regs[1]==0xe0400);unsigned total=calls;n++;for(unsigned i=1;i<=total;i++)for(unsigned m=0;m<2;m++){init(&r);fail=i;afterwrite=m;assert(diagnostic_usb4_endpoint_scan(&r,15)==-EIO);if(i<=9)assert(regs[0]==0xe0400&&regs[1]==0xe0400);n++;}init(&r);regs[1]|=1U<<31;assert(diagnostic_usb4_endpoint_scan(&r,15)==-EBUSY&&!link&&!scan);n++;init(&r);regs[0]|=1U<<25;assert(diagnostic_usb4_endpoint_scan(&r,15)==-EBUSY&&!link&&!scan);n++;printf("CASES %u PASS; transactions %u; bounded NVMe read callback sequenced before adapter shutdown\n",n,total);}
''';(p/'test.c').write_text(c);subprocess.run(['cc','-Wall','-Wextra','-Wno-unused-parameter','-fsanitize=address,undefined',str(p/'test.c'),'-o',str(p/'test')],check=True);r=subprocess.run([str(p/'test')],capture_output=True,text=True);(p/'test.log').write_text(r.stdout+r.stderr);assert r.returncode==0,r.stderr;(p/'result.json').write_text(json.dumps({'passed':True,'summary':r.stdout.splitlines()[-1],'ASan':True,'UBSan':True},indent=2)+'\n');print(r.stdout.splitlines()[-1])
