from pathlib import Path
import subprocess,json
w=Path(__file__).resolve().parent;p=w/'preflight-tests';p.mkdir(exist_ok=True);s=(w/'source/cmd/apple_nhi_m1_inventory.c').read_text();(p/'actual.inc').write_text(s[s.index('int apple_nhi_m1_usb4_preflight'):s.index('/* USB4 protocol-adapter credit/IFC')])
c=r'''#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <errno.h>
#include <assert.h>
#include <string.h>
typedef uint32_t u32;
typedef int(*apple_nhi_read_fn)(void*,unsigned,unsigned,unsigned,unsigned,u32*);
#include "snapshot.h"
#include "actual.inc"
static struct apple_usb4_snapshot snap;
static u32 h[2][5],regs[2][17][256],paths[2][17][18];static unsigned calls,fail;
static int rd(unsigned route,unsigned port,unsigned space,unsigned off,unsigned n,u32*d){calls++;if(calls==fail)return -EIO;assert(route<2&&port<=16&&off+n<=256&&n<=8);if(space==2){assert(!port&&!off&&n==5);memcpy(d,h[route],20);}else if(space==1){assert(port);if((regs[route][port][2]&0xffffff)!=1 && off>=9)assert(off==9&&n==1);memcpy(d,regs[route][port]+off,n*4);}else{assert(space==0&&n==2&&(off==0||off==16));memcpy(d,paths[route][port]+off,n*4);}return 0;}
static int hr(void*x,unsigned p,unsigned s,unsigned o,unsigned n,u32*d){return rd(0,p,s,o,n,d);}static int rr(void*x,unsigned p,unsigned s,unsigned o,unsigned n,u32*d){return rd(1,p,s,o,n,d);}
static void init(void){memset(h,0,sizeof h);memset(regs,0,sizeof regs);memset(paths,0,sizeof paths);calls=fail=0;for(unsigned r=0;r<2;r++){h[r][1]=(4<<14)|(1<<8)|(r<<20);h[r][2]=r;h[r][3]=1U<<31;h[r][4]=0x200010ff;for(unsigned p=1;p<=4;p++){regs[r][p][3]=p<<20;regs[r][p][5]=0x4008;}for(unsigned p=1;p<=2;p++){regs[r][p][2]=1;regs[r][p][1]=0x40;regs[r][p][0x40]=0x380;regs[r][p][0x80]=0x100;}regs[r][3][2]=r?0x100102:0x100101;regs[r][3][1]=9;regs[r][3][9]=0x400;}}
static int run(void){return apple_nhi_m1_usb4_preflight(hr,rr,0,&snap);}
int main(void){unsigned n=0;init();assert(!run());unsigned total=calls;n++;for(unsigned i=1;i<=total;i++){init();fail=i;assert(run()==-EIO&&calls==i);n++;}init();h[1][2]=2;assert(run()==-EPROTO);n++;init();h[1][1]&=~(63U<<8);assert(run()==-EPROTO);n++;init();regs[1][4][2]=0x100102;assert(run()==-EOPNOTSUPP);n++;init();regs[1][3][2]=0;assert(run()==-ENODEV);n++;init();regs[1][3][3]=4<<20;assert(run()==-EPROTO);n++;init();regs[1][3][9]|=1U<<31;assert(run()==-EBUSY);n++;init();paths[1][1][16]=1U<<31;assert(run()==-EBUSY);n++;init();regs[1][1][0x80]=0x280;assert(run()==-ELOOP);n++;init();regs[1][3][5]=0;assert(run()==-ENOSPC);n++;init();assert(apple_nhi_m1_usb4_preflight(0,rr,0,&snap)==-EINVAL&&!calls);n++;printf("CASES %u PASS; transaction failure injection %u\n",n,total);}
''';(p/'test.c').write_text(c);subprocess.run(['cc','-Wall','-Wextra','-Wno-unused-parameter','-fsanitize=address,undefined',str(p/'test.c'),'-o',str(p/'test')],check=True);r=subprocess.run([str(p/'test')],capture_output=True,text=True);(p/'test.log').write_text(r.stdout+r.stderr);assert r.returncode==0,r.stderr;(p/'result.json').write_text(json.dumps({'passed':True,'summary':r.stdout.splitlines()[-1],'ASan':True,'UBSan':True,'PCIe_capability_register_width':'one DWORD, mock rejects adjacent read'},indent=2)+'\n');print(r.stdout.splitlines()[-1])
