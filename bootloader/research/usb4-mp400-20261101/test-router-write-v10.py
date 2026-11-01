from pathlib import Path
import subprocess,json
w=Path(__file__).resolve().parent;p=w/'router-tests';s=(w/'source/cmd/apple_nhi_m1_ring.c').read_text();s=s[s.index('static int diagnostic_usb4_router_write'):s.index('static void diagnostic_usb4_wait')];(p/'write.inc').write_text(s)
c=r'''#include <stdint.h>
#include <stdbool.h>
#include <errno.h>
#include <assert.h>
#include <string.h>
#include <stdio.h>
typedef uint32_t u32;
#define BIT(n) (1U<<(n))
#define USB4_CFG_WRITE 2
static unsigned writes;
static int diagnostic_xfer(void*x,unsigned p,unsigned s,unsigned off,unsigned n,u32*d,unsigned op,unsigned route){assert(!p&&s==2&&route==1&&op==USB4_CFG_WRITE);assert((off==1&&n==4)||(off==5&&n==1));writes++;return 0;}
#include "write.inc"
int main(void){u32 d[4]={0x1101c0,1,BIT(31),0x200010ff};unsigned n=0;assert(!diagnostic_usb4_router_write(0,1,4,d));n++;for(unsigned o=0;o<256;o++){if(o==1)continue;assert(diagnostic_usb4_router_write(0,o,4,d)==-EINVAL);n++;}assert(diagnostic_usb4_router_write(0,1,4,0)==-EINVAL);n++;for(unsigned i=0;i<4;i++){u32 c[4];memcpy(c,d,sizeof d);if(i==0)c[0]&=~(7U<<20);else c[i]=0;assert(diagnostic_usb4_router_write(0,1,4,c)==-EINVAL);n++;}d[0]=0x03000000;assert(!diagnostic_usb4_router_write(0,5,1,d));n++;d[0]=0x83000000;assert(!diagnostic_usb4_router_write(0,5,1,d));n++;d[0]|=1;assert(diagnostic_usb4_router_write(0,5,1,d)==-EINVAL);n++;d[0]=0x83800000;assert(diagnostic_usb4_router_write(0,5,1,d)==-EINVAL);n++;assert(writes==3);printf("CASES %u PASS\n",n);}
''';(p/'write-test.c').write_text(c)
subprocess.run(['cc','-Wall','-Wextra','-Wno-unused-parameter','-fsanitize=address,undefined',str(p/'write-test.c'),'-o',str(p/'write-test')],check=True)
r=subprocess.run([str(p/'write-test')],capture_output=True,text=True);assert r.returncode==0,r.stderr;(p/'write-result.json').write_text(json.dumps({'passed':True,'summary':r.stdout.strip(),'ASan':True,'UBSan':True},indent=2)+'\n');print(r.stdout)
