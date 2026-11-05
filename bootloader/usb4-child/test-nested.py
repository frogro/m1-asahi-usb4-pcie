from pathlib import Path
import sys
import shutil,subprocess as sp
p=Path(__file__).parent;s=Path(sys.argv[1]);w=Path(sys.argv[2])/'nested-tests';w.mkdir(parents=True,exist_ok=True);inc=w/'include';shutil.copytree(p/'fixtures/include',inc,dirs_exist_ok=True);shutil.copyfile(s/'include/apple_nhi_m1.h',inc/'apple_nhi_m1.h')
head=r'''
#include <apple_nhi_m1.h>
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#define BIT(n) (1U<<(n))
#define RING_COUNT 512
#define USB4_CFG_READ 1
#define USB4_CFG_WRITE 2
struct diagnostic_ring{bool automatic,child_usb4;unsigned capacity;struct apple_usb4_snapshot usb4_snapshot,auto_usb_snapshot;unsigned sent,received;u64 child_route;unsigned child_max_port,child_upstream,child_pcie;struct apple_nhi_child child;u32 identity[2][64][4];bool identity_valid[2][64];bool host_credit_valid;u32 host_credit_meta,host_credit_data[16];};
static u32 h[3][5],ph[3][64][256],path[3][64][20];static unsigned calls,fail,pathwrites,enables,starts,scans,reads,activate,plan_only,childlimit;static int scanret;
static int ofnode_path(const char*x){(void)x;return 0;}
static int ofnode_read_bool(int x,const char*n){(void)x;if(!strcmp(n,"u-boot,downstream-pcie-plan-only"))return plan_only;assert(!strcmp(n,"u-boot,downstream-pcie-activate"));return activate;}
static void udelay(unsigned x){(void)x;}
static int diagnostic_xfer(struct diagnostic_ring*r,unsigned p,unsigned sp,unsigned o,unsigned n,u32*d,unsigned op,u64 route){unsigned ix=route==0?0:route==1?1:2;assert(route==0||route==1||route==0x301);assert(p<64);r->sent++;r->received++;calls++;if(calls==fail)return -EIO;if(sp==2&&o>=9){assert((route==1||route==0x301)&&!p);if(op==2){assert(n==1&&(o==0x19||o==0x1a));return 0;}if(o==0x19){assert(n==1);d[0]=2;}else if(o==0x1a){assert(n==1);d[0]=0x33;}else{assert(o==9&&n==16);memset(d,0,64);d[0]=4|((route==1?6:childlimit)<<16);d[1]=1|(8<<16);}return 0;}if(sp==2){assert(op==1&&!p&&!o&&n==5);memcpy(d,h[ix],20);return 0;}assert(sp==0||sp==1);if(sp==1 && op==1 && o==8 && (ph[ix][p][2]==0x100101 || ph[ix][p][2]==0x100102))assert(n==1);if(op==1)memcpy(d,sp==0?path[ix][p]+o:ph[ix][p]+o,n*4);else{assert(op==2);if(sp==0){assert(o==16&&n==2);pathwrites++;memcpy(path[ix][p]+o,d,8);}else{assert(o==8&&n==1&&(*d&BIT(31)));enables++;ph[ix][p][o]=*d;}}return 0;}
static int test_host(void*x,unsigned p,unsigned sp,unsigned o,unsigned n,u32*d){return diagnostic_xfer(x,p,sp,o,n,d,USB4_CFG_READ,0);}
static int test_parent(void*x,unsigned p,unsigned sp,unsigned o,unsigned n,u32*d){return diagnostic_xfer(x,p,sp,o,n,d,USB4_CFG_READ,1);}
static int apple_pciec_m1_start_link(void){starts++;assert(enables==4);return 0;}
static int apple_pciec_m1_scan(void){scans++;return scanret;}
static int apple_pciec_m1_nvme_read(void){reads++;assert(scans==1&&starts==1&&enables==4&&pathwrites==8);return 0;}
'''
main=r'''
static void port(unsigned r,unsigned p,unsigned type){ph[r][p][1]=8;ph[r][p][2]=type;ph[r][p][3]=p<<20;ph[r][p][4]=60<<20;ph[r][p][5]=19|(19<<11);ph[r][p][8]=(type==1?1:4)<<8;ph[r][p][9]=type==1?2<<26:0;path[r][p][0]=2<<17;}
static void init(struct diagnostic_ring*r){memset(r,0,sizeof(*r));r->capacity=256;memset(h,0,sizeof h);memset(ph,0,sizeof ph);memset(path,0,sizeof path);calls=fail=pathwrites=enables=starts=scans=reads=scanret=0;activate=1;plan_only=0;childlimit=6;for(unsigned i=0;i<3;i++){h[i][0]=0x12348086;h[i][1]=((i==0?7:i==1?19:11)<<14)|(i<<20)|(i?1<<8:0);h[i][2]=i==2?0x301:i;h[i][3]=BIT(31);h[i][4]=i==2?0x020000ff:1U<<29;}port(0,1,1);port(0,3,0x100101);port(1,1,1);port(1,3,1);port(1,9,0x100102);port(1,10,0x100101);port(2,1,1);port(2,6,0x100102);r->child_route=0x301;r->child_max_port=11;r->child_upstream=1;r->child_pcie=6;r->child=(struct apple_nhi_child){0x301,3,10};r->host_credit_valid=true;r->host_credit_meta=1;r->host_credit_data[0]=4|(6<<16);for(unsigned i=0;i<2;i++)for(unsigned p=1;p<64;p++){memcpy(r->identity[i][p],ph[i][p],16);r->identity_valid[i][p]=true;}}
#define C(e) do{assert(e);cases++;}while(0)
int main(void){struct diagnostic_ring r;unsigned cases=0,base;init(&r);C(!diagnostic_nested_pcie(&r)&&reads==1);base=calls;C(path[0][3][16]==0x80000808);C(path[1][10][16]==0x80001808);C(path[2][1][16]==0x80203008);C(path[2][6][16]==0x800e0808);for(unsigned f=1;f<=base;f++){init(&r);fail=f;C(diagnostic_nested_pcie(&r)==-EIO&&calls==f&&!reads);}init(&r);activate=0;C(diagnostic_nested_pcie(&r)==-EINPROGRESS&&!pathwrites&&!enables&&!reads);init(&r);r.sent=r.received=210;C(diagnostic_nested_pcie(&r)==-ENOSPC&&!pathwrites&&!enables);init(&r);scanret=-ENODEV;C(diagnostic_nested_pcie(&r)==-ENODEV&&!reads&&scans==1);for(unsigned m=0;m<8;m++){init(&r);switch(m){case 0:r.child.route=0x401;break;case 1:ph[2][6][2]=0;break;case 2:ph[2][1][9]=7<<26;break;case 3:path[2][6][16]=BIT(31);break;case 4:r.host_credit_valid=false;break;case 5:r.host_credit_data[0]=4|(5<<16);break;case 6:ph[2][1][4]=16<<20;break;case 7:ph[1][10][8]|=BIT(31);break;}C(diagnostic_nested_pcie(&r)<0&&!pathwrites&&!enables&&!reads);}init(&r);r.automatic=true;r.capacity=512;activate=0;C(!diagnostic_nested_pcie(&r)&&reads==1);init(&r);r.automatic=true;r.capacity=512;r.sent=r.received=470;C(diagnostic_nested_pcie(&r)==-ENOSPC&&!pathwrites);init(&r);r.automatic=true;r.capacity=512;port(0,4,0x200101);port(1,16,0x200102);for(unsigned i=0;i<2;i++)for(unsigned q=1;q<64;q++)memcpy(r.identity[i][q],ph[i][q],16);unsigned protocols=0;C(!apple_nhi_m1_auto_preflight(test_host,test_parent,&r,&r.usb4_snapshot,&r.auto_usb_snapshot,&protocols)&&protocols==3);r.host_credit_meta=2;r.host_credit_data[1]=1|(8<<16);activate=0;C(!diagnostic_nested_pcie(&r)&&reads==1);init(&r);r.automatic=true;r.capacity=512;r.auto_usb_snapshot.valid=true;C(diagnostic_nested_pcie(&r)==-EPROTO&&!pathwrites);init(&r);r.child_usb4=true;h[2][4]=0x200010ff;C(!diagnostic_nested_pcie(&r)&&reads==1);unsigned usb4calls=calls;C(path[2][1][16]==0x800c3008 && path[2][6][16]==0x80000808);
for(unsigned f=1;f<=usb4calls;f++){init(&r);r.child_usb4=true;h[2][4]=0x200010ff;fail=f;C(diagnostic_nested_pcie(&r)==-EIO&&calls==f&&!reads);}
init(&r);r.child_usb4=true;h[2][4]=0x200010ff;childlimit=5;C(diagnostic_nested_pcie(&r)==-ENOSPC&&!pathwrites&&!enables);
init(&r);r.child_usb4=true;h[2][4]=0x200010ff;ph[2][1][4]=7<<20;C(diagnostic_nested_pcie(&r)==-ENOSPC&&!pathwrites);
init(&r);r.child_usb4=true;h[2][4]=0x200010ff;r.automatic=true;r.capacity=512;plan_only=1;C(diagnostic_nested_pcie(&r)==-EINPROGRESS&&!pathwrites&&!enables&&!reads);
init(&r);r.child_usb4=true;h[2][4]=0x200010ff;r.automatic=true;r.capacity=512;port(0,4,0x200101);port(1,16,0x200102);for(unsigned i=0;i<2;i++)for(unsigned q=1;q<64;q++)memcpy(r.identity[i][q],ph[i][q],16);unsigned usb4_protocols=0;C(!apple_nhi_m1_auto_preflight(test_host,test_parent,&r,&r.usb4_snapshot,&r.auto_usb_snapshot,&usb4_protocols)&&usb4_protocols==3);r.host_credit_meta=2;r.host_credit_data[1]=1|(8<<16);C(!diagnostic_nested_pcie(&r)&&reads==1);printf("PASS %u nested planning/activation/fault cases; nominal transactions=%u\n",cases,base);}
'''
(w/'nested.c').write_text(head+(s/'cmd/apple_nhi_m1_nested.inc').read_text()+main)
sp.run(['cc','-g','-O1','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-I'+str(inc),str(w/'nested.c'),str(s/'cmd/apple_nhi_m1_inventory.c'),'-o',str(w/'nested-test')],check=True)
r=sp.run([str(w/'nested-test')],capture_output=True,text=True);(w/'nested.log').write_text(r.stdout+r.stderr);print((r.stdout+r.stderr)[-1500:]);r.check_returncode()
