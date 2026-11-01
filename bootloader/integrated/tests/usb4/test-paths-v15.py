from pathlib import Path
import subprocess,json
w=Path(__file__).resolve().parent;p=w/'path-tests';p.mkdir(exist_ok=True);ring=(w/'source/cmd/apple_nhi_m1_ring.c').read_text();inv=(w/'source/cmd/apple_nhi_m1_inventory.c').read_text();(p/'actual.inc').write_text(inv[inv.index('int apple_nhi_m1_usb4_path_plan'):]+ring[ring.index('static int diagnostic_usb4_paths'):ring.index('/* USB4 v1 router registers only.')])
c=r'''#include <stdint.h>
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
static int diagnostic_usb4_endpoint_scan(struct diagnostic_ring*r,unsigned int mode){assert(0);return -EIO;}
static unsigned calls,fail,afterwrite,badread;static u32 paths[2][17][2],initial[2][17][2],lim[2];
static int diagnostic_query(struct diagnostic_ring*r,unsigned op,unsigned meta){assert(op==0x33&&!meta);calls++;return calls==fail?-EIO:0;}
static int diagnostic_xfer(struct diagnostic_ring*r,unsigned port,unsigned space,unsigned offset,unsigned words,u32*d,unsigned type,unsigned route){assert(route<2);calls++;if(calls==fail&&!afterwrite)return -EIO;if(space==2){assert(!port&&type==USB4_CFG_READ);if(offset==0x19){assert(words==1);*d=1;}else{assert(offset==9&&words==16);memset(d,0,64);d[0]=(lim[route]<<16)|4;}}else{assert(space==0&&offset==16&&words==2&&port<17);if(type==USB4_CFG_READ){memcpy(d,paths[route][port],8);if(calls==badread)d[1]^=1;}else{assert(type==USB4_CFG_WRITE);memcpy(paths[route][port],d,8);}}if(calls==fail)return -EIO;return 0;}
#include "actual.inc"
static void init(struct diagnostic_ring*r){memset(r,0,sizeof *r);memset(paths,0,sizeof paths);calls=fail=afterwrite=badread=0;lim[0]=70;lim[1]=64;struct apple_usb4_snapshot*s=&r->usb4_snapshot;s->valid=true;s->port[0]=s->port[3]=3;s->port[1]=s->port[2]=1;s->cap[0]=s->cap[3]=9;s->cap[1]=17;s->cap[2]=128;s->nfc[1]=174<<20;s->nfc[2]=66<<20;s->control[1]=s->control[2]=2<<17;s->old[3][0]=8|(5<<17);s->old[3][1]=1<<26;memcpy(paths[1][3],s->old[3],8);memcpy(initial,paths,sizeof paths);}
int main(void){struct diagnostic_ring r;u32 plan[4][2],l[2]={70,64};unsigned n=0;init(&r);assert(!apple_nhi_m1_usb4_path_plan(&r.usb4_snapshot,l,plan));assert((plan[3][0]&(127<<17))==(5<<17));assert((plan[3][1]&((1<<24)|(1<<26)))==(1<<26));assert(((plan[2][0]>>11)&63)==3);assert(((plan[1][0]>>11)&63)==3);n++;assert(!diagnostic_usb4_paths(&r,false)&&!memcmp(paths,initial,sizeof paths));unsigned total=calls;n++;for(unsigned i=1;i<=total;i++)for(unsigned mode=0;mode<2;mode++){init(&r);fail=i;afterwrite=mode;assert(diagnostic_usb4_paths(&r,false)==-EIO);if(i<18)assert(!memcmp(paths,initial,sizeof paths));n++;}init(&r);r.usb4_snapshot.old[2][0]=1U<<31;assert(apple_nhi_m1_usb4_path_plan(&r.usb4_snapshot,l,plan)==-EBUSY);n++;init(&r);l[1]=5;assert(apple_nhi_m1_usb4_path_plan(&r.usb4_snapshot,l,plan)==-ENOSPC);n++;l[1]=64;init(&r);r.usb4_snapshot.nfc[2]=7<<20;assert(apple_nhi_m1_usb4_path_plan(&r.usb4_snapshot,l,plan)==-ENOSPC);n++;init(&r);r.usb4_snapshot.port[3]=1;assert(apple_nhi_m1_usb4_path_plan(&r.usb4_snapshot,l,plan)==-EPROTO);n++;init(&r);badread=8;assert(diagnostic_usb4_paths(&r,false)==-EIO&&!memcmp(paths,initial,sizeof paths));n++;printf("CASES %u PASS; full programming/restore transactions %u\n",n,total);}
''';(p/'test.c').write_text(c);subprocess.run(['cc','-Wall','-Wextra','-fsanitize=address,undefined',str(p/'test.c'),'-o',str(p/'test')],check=True);r=subprocess.run([str(p/'test')],capture_output=True,text=True);(p/'test.log').write_text(r.stdout+r.stderr);assert r.returncode==0,r.stderr;(p/'result.json').write_text(json.dumps({'passed':True,'summary':r.stdout.splitlines()[-1],'ASan':True,'UBSan':True,'scope':'actual path plan, programming, verification and rollback; injected before/after transfer failures; protocol-adapter credit/IFC/ISE preserved'},indent=2)+'\n');print(r.stdout.splitlines()[-1])
