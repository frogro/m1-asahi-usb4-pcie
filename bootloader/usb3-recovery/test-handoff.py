from pathlib import Path
import sys
import subprocess
p=Path(sys.argv[2]);p.mkdir(parents=True,exist_ok=True);t=(Path(sys.argv[1])/'drivers/usb/host/xhci.c').read_text();a=t.index('int xhci_m1_os_handoff(');b=t.index('\n#endif',a);body=t[a:b]
pre=r'''
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <assert.h>
#include <errno.h>
typedef uint32_t u32;typedef uint64_t u64;
#define CMD_RUN 1
#define CMD_RESET 2
#define STS_HALT 1
#define STS_CNR 2048
#define STS_FATAL 4
#define STS_HCE 4096
struct xhci_hcor {u32 or_usbcmd,or_usbsts;u64 or_dcbaap,or_crcr;};
struct xhci_ctrl {bool m1_diag;struct xhci_hcor*hcor;};
static int stop_result,reset_result,stops,resets;
static int xhci_m1_diag_stop(struct xhci_ctrl*c){assert(c&&c->hcor);stops++;return stop_result;}
static int xhci_reset(struct xhci_hcor*h){assert(h);assert(stops);resets++;return reset_result;}
static u32 xhci_readl(u32*p){return *p;}
static u64 xhci_readq(u64*p){return *p;}
'''
post=r'''
int main(void){unsigned checks=0;struct xhci_hcor h;struct xhci_ctrl c;
#define C(x) do{assert(x);checks++;}while(0)
#define RESET() do{h=(struct xhci_hcor){.or_usbsts=1};c=(struct xhci_ctrl){.m1_diag=true,.hcor=&h};stop_result=reset_result=stops=resets=0;}while(0)
RESET();C(!xhci_m1_os_handoff(&c));C(stops==1&&resets==1);
RESET();C(xhci_m1_os_handoff(NULL)==-EINVAL);C(!stops&&!resets);
RESET();c.m1_diag=false;C(xhci_m1_os_handoff(&c)==-EINVAL);C(!stops&&!resets);
RESET();c.hcor=NULL;C(xhci_m1_os_handoff(&c)==-EINVAL);C(!stops&&!resets);
RESET();stop_result=-EBUSY;C(xhci_m1_os_handoff(&c)==-EBUSY);C(stops==1&&!resets);
RESET();reset_result=-ETIMEDOUT;C(xhci_m1_os_handoff(&c)==-ETIMEDOUT);C(stops==1&&resets==1);
for(unsigned bit=0;bit<2;bit++){RESET();h.or_usbcmd=1<<bit;C(xhci_m1_os_handoff(&c)==-EIO);}
for(unsigned bit=0;bit<3;bit++){RESET();h.or_usbsts|=(u32[]){STS_CNR,STS_FATAL,STS_HCE}[bit];C(xhci_m1_os_handoff(&c)==-EIO);}
RESET();h.or_usbsts=0;C(xhci_m1_os_handoff(&c)==-EIO);
for(unsigned bit=6;bit<64;bit++){RESET();h.or_dcbaap=1ULL<<bit;C(xhci_m1_os_handoff(&c)==-EIO);RESET();h.or_crcr=1ULL<<bit;C(xhci_m1_os_handoff(&c)==-EIO);}
printf("PASS %u actual-source handoff assertions\n",checks);return 0;}
'''
f=p/'handoff-harness.c';f.write_text(pre+body+post);subprocess.run(['cc','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-g',str(f),'-o',str(p/'handoff-harness')],check=True);r=subprocess.run([str(p/'handoff-harness')],capture_output=True,text=True);(p/'handoff-tests.log').write_text(r.stdout+r.stderr);r.check_returncode();print(r.stdout.splitlines()[-1])
