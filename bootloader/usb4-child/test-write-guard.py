from pathlib import Path
import sys
import subprocess
b=Path(__file__).parent;p=Path(sys.argv[2])/'guard-tests';p.mkdir(parents=True,exist_ok=True)
s=(Path(sys.argv[1])/'cmd/apple_nhi_m1_ring.c').read_text();s=s[s.index('static int diagnostic_child_usb4_write('):s.index('static void diagnostic_child_wait')]
(p/'actual.inc').write_text(s)
c=r'''#include <stdint.h>
#include <string.h>
#include <assert.h>
#include <errno.h>
#include <stdio.h>
typedef uint32_t u32;typedef uint64_t u64;
#define BIT(n) (1U<<(n))
#define USB4_CFG_WRITE 2
struct diagnostic_ring {int unused;};
struct child_config_context {struct diagnostic_ring *ring;u64 route;unsigned upstream,max;};
static unsigned writes;static u64 last_route;
static int diagnostic_xfer(struct diagnostic_ring*r,unsigned p,unsigned s,unsigned o,unsigned n,u32*d,unsigned op,u64 route){assert(!p&&s==2&&op==2);assert((o==1&&n==4)||(o==5&&n==1));writes++;last_route=route;return 0;}
#include "actual.inc"
int main(void){struct diagnostic_ring r;struct child_config_context c={&r,0x301,1,4};u32 d[4]={(4U<<14)|(1U<<8)|(2U<<20),0x301,BIT(31),0x200010ff};unsigned cases=0;
assert(!diagnostic_child_usb4_write(&c,1,4,d)&&writes==1&&last_route==0x301);cases++;
for(unsigned i=0;i<4;i++)for(unsigned bit=0;bit<32;bit++){u32 bad[4];memcpy(bad,d,16);bad[i]^=BIT(bit);unsigned w=writes;int e=diagnostic_child_usb4_write(&c,1,4,bad);if(e)assert(writes==w);else assert(writes==w+1);if(i==1||i==2||(i==3&&bit<16)||(i==0&&bit>=8&&bit<=22))assert(e==-EINVAL);cases++;}
for(unsigned off=0;off<32;off++)for(unsigned n=0;n<=5;n++){u32 v=BIT(24);unsigned w=writes;int e=diagnostic_child_usb4_write(&c,off,n,&v);if(off==1&&n==4)continue;if(off==5&&n==1)assert(!e);else assert(e==-EINVAL&&writes==w);cases++;}
u32 v=BIT(24)|BIT(31);assert(!diagnostic_child_usb4_write(&c,5,1,&v));cases++;
for(unsigned bit=0;bit<2;bit++){v=BIT(24)|(bit?BIT(23):BIT(0));unsigned w=writes;assert(diagnostic_child_usb4_write(&c,5,1,&v)==-EINVAL&&writes==w);cases++;}
assert(diagnostic_child_usb4_write(0,1,4,d)==-EINVAL);cases++;
printf("CASES %u PASS\n",cases);}
'''
# Avoid invoking header path with a short array in the malformed-size matrix.
c=c.replace('u32 v=BIT(24);unsigned w=writes;', 'u32 v[4]={BIT(24),0,0,0};unsigned w=writes;').replace('(&c,off,n,&v)', '(&c,off,n,v)')
(p/'test.c').write_text(c)
subprocess.run(['cc','-Wall','-Wextra','-Wno-unused-parameter','-fsanitize=address,undefined','-g',str(p/'test.c'),'-o',str(p/'test')],check=True)
r=subprocess.run([str(p/'test')],capture_output=True,text=True);(p/'test.log').write_text(r.stdout+r.stderr);assert r.returncode==0,r.stdout+r.stderr;print(r.stdout)
