from pathlib import Path
import sys
import subprocess,json
w=Path(__file__).resolve().parent;p=Path(sys.argv[2])/'router-tests';p.mkdir(parents=True,exist_ok=True)
s=(Path(sys.argv[1])/'cmd/apple_nhi_m1_inventory.c').read_text();s=s[s.index('int apple_nhi_m1_usb4_router_setup'):s.index('/* Read-only single-hop USB4 path discovery.')];(p/'actual.inc').write_text(s)
c=r'''#include <stdint.h>
#include <stdio.h>
#include <stdbool.h>
#include <errno.h>
#include <assert.h>
#include <string.h>
typedef uint32_t u32; typedef uint64_t u64;
#define APPLE_NHI_ROUTER_MAX_PORT 63
typedef int(*apple_nhi_read_fn)(void*,unsigned,unsigned,unsigned,unsigned,u32*);
typedef int(*apple_nhi_router_write_fn)(void*,unsigned,unsigned,const u32*);
#include "actual.inc"
static u32 rem[8],host[5],types[64];static unsigned calls,fail,wr,waits,rr,cr;static bool corrupt;
static int tick(void){calls++;return calls==fail?-EIO:0;}
static int rd(void*x,unsigned port,unsigned space,unsigned off,unsigned n,u32*d){assert(!port&&space==2&&off+n<=8);int r=tick();if(r)return r;if(off==6){rem[6]&=~(3U<<24);if(rr)rem[6]|=1U<<24;if(cr&&(rem[5]>>31))rem[6]|=1U<<25;}memcpy(d,rem+off,n*4);if(corrupt&&off==1)d[0]^=1;return 0;}
static int hr(void*x,unsigned port,unsigned space,unsigned off,unsigned n,u32*d){int r=tick();if(r)return r;assert(!off);if(!port){assert(space==2&&n==5);memcpy(d,host,20);}else{assert(space==1&&n==4&&port<64);memset(d,0,16);d[2]=types[port];d[3]=port<<20;}return 0;}
static int wt(void*x,unsigned off,unsigned n,const u32*d){assert((off==1&&n==4)||(off==5&&n==1));int r=tick();if(r)return r;wr++;memcpy(rem+off,d,n*4);return 0;}
static void waitfn(void*x){waits++;assert(waits<=100);}
static void init(void){memset(rem,0,sizeof rem);memset(host,0,sizeof host);memset(types,0,sizeof types);rem[0]=0x2463174c;rem[1]=0x101c0;rem[4]=0x2000000a;host[0]=0x200005ac;host[1]=7<<14;host[3]=1U<<31;host[4]=0x200010ff;types[1]=types[2]=1;types[3]=0x100101;types[4]=0x200101;types[5]=types[6]=0xe0101;types[7]=2;calls=fail=wr=waits=0;rr=cr=1;corrupt=false;}
static int run(void){return apple_nhi_m1_usb4_router_setup(hr,rd,wt,waitfn,0,1);}
int main(void){unsigned cases=0;init();assert(!run()&&wr==3&&rem[5]==0x83000000&&rem[6]==0x03000000);unsigned total=calls;cases++;for(unsigned i=1;i<=total;i++){init();fail=i;assert(run()==-EIO&&calls==i);cases++;}init();rr=0;assert(run()==-ETIMEDOUT&&waits==50&&wr==2&&!(rem[5]>>31));cases++;init();cr=0;assert(run()==-ETIMEDOUT&&waits==50&&wr==3);cases++;init();types[3]=0;assert(run()==-EOPNOTSUPP&&!wr);cases++;init();types[4]=0;rem[6]=1<<18;assert(!run()&&rem[5]==0x85000000);cases++;init();rem[4]=0x40000000;assert(run()==-EPROTONOSUPPORT&&!wr);cases++;init();rem[2]=1;assert(run()==-EBUSY&&!wr);cases++;init();host[3]=0;assert(run()==-EPROTO&&!wr);cases++;init();corrupt=true;assert(run()==-EIO&&wr==1);cases++;init();rem[5]=1U<<31;assert(run()==-EBUSY&&wr==1);cases++;init();rem[5]=1;assert(run()==-EBUSY&&wr==1);cases++;init();assert(apple_nhi_m1_usb4_router_setup(hr,rd,wt,waitfn,0,0)==-EINVAL&&!calls);cases++;init();assert(apple_nhi_m1_usb4_router_setup(0,rd,wt,waitfn,0,1)==-EINVAL&&!calls);cases++;for(unsigned lane=1;lane<=63;lane++) {
 init();host[1]=(63U<<14)|(1U<<20);host[2]=1;types[lane]=1;
 if(lane==3)types[5]=0x100101;
 assert(!apple_nhi_m1_usb4_router_setup_route(hr,rd,wt,waitfn,0,1,1ULL|(lane<<8),2));
 assert(rem[2]==(1U|(lane<<8)) && ((rem[1]>>20)&7)==2 && rem[4]==0x200010ff);cases++;
}
init();host[1]|=1U<<20;host[2]=1;
assert(!apple_nhi_m1_usb4_router_setup_route(hr,rd,wt,waitfn,0,1,0x301,2));unsigned childcalls=calls;
for(unsigned n=1;n<=childcalls;n++) {init();host[1]|=1U<<20;host[2]=1;fail=n;assert(apple_nhi_m1_usb4_router_setup_route(hr,rd,wt,waitfn,0,1,0x301,2)==-EIO && calls==n);cases++;}
u64 routes[]={0,1,0x300,0x4001,0x10101};
for(unsigned n=0;n<5;n++){init();assert(apple_nhi_m1_usb4_router_setup_route(hr,rd,wt,waitfn,0,1,routes[n],2)==-EINVAL&&!calls);cases++;}
for(unsigned n=0;n<4;n++){init();host[1]|=1U<<20;host[2]=1;if(n==0)host[2]=2;if(n==1)host[1]&=~(7U<<20);if(n==2)host[0]=0;if(n==3)host[1]=(host[1]&~(63U<<14))|(2U<<14);assert(apple_nhi_m1_usb4_router_setup_route(hr,rd,wt,waitfn,0,1,0x301,2)==-EPROTO&&!wr);cases++;}
for(unsigned n=0;n<2;n++){init();host[1]|=1U<<20;host[2]=1;if(n)cr=0;else rr=0;assert(apple_nhi_m1_usb4_router_setup_route(hr,rd,wt,waitfn,0,1,0x301,2)==-ETIMEDOUT&&waits==50);cases++;}
printf("CASES %u PASS; transaction failure injection %u\n",cases,total);}
''';(p/'test.c').write_text(c)
subprocess.run(['cc','-Wall','-Wextra','-Wno-unused-parameter','-fsanitize=address,undefined','-g',str(p/'test.c'),'-o',str(p/'test')],check=True)
r=subprocess.run([str(p/'test')],capture_output=True,text=True);(p/'test.log').write_text(r.stdout+r.stderr);assert r.returncode==0,r.stderr
(p/'result.json').write_text(json.dumps({'passed':True,'summary':r.stdout.splitlines()[-1],'ASan':True,'UBSan':True},indent=2)+'\n');print(r.stdout.splitlines()[-1])
