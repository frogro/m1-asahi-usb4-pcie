from pathlib import Path
import subprocess,json
w=Path(__file__).resolve().parent;p=w/'router-tests';s=(w/'source/cmd/apple_nhi_m1_ring.c').read_text();(p/'credit.inc').write_text(s[s.index('static int diagnostic_usb4_credit_read'):s.index('static void diagnostic_usb4_credit_wait')]);c=r'''#include <stdint.h>
#include <errno.h>
#include <assert.h>
#include <stdio.h>
typedef uint32_t u32;
#define USB4_CFG_WRITE 2
#define USB4_CFG_READ 1
static unsigned calls;
static int diagnostic_xfer(void*x,unsigned p,unsigned s,unsigned off,unsigned n,u32*d,unsigned op,unsigned route){assert(!p&&s==2&&route==1);calls++;return 0;}
#include "credit.inc"
int main(void){u32 d[16]={0};unsigned n=0;for(unsigned off=0;off<256;off++){int r=diagnostic_usb4_credit_write(0,off,0);assert(r==((off==0x19)?0:-EINVAL));n++;r=diagnostic_usb4_credit_write(0,off,0x80000033);assert(r==((off==0x1a)?0:-EINVAL));n++;}for(unsigned op=0;op<256;op++){assert(diagnostic_usb4_credit_write(0,0x1a,0x80000000|op)==(op==0x33?0:-EINVAL));n++;}for(unsigned off=0;off<256;off++)for(unsigned len=1;len<=16;len++){int expected=((len==1&&(off==0x19||off==0x1a))||(len==16&&off==9))?0:-EINVAL;assert(diagnostic_usb4_credit_read(0,0,2,off,len,d)==expected);n++;}assert(diagnostic_usb4_credit_read(0,1,2,0x19,1,d)==-EINVAL);n++;printf("CASES %u PASS\n",n);}
''';(p/'credit-test.c').write_text(c);subprocess.run(['cc','-Wall','-Wextra','-Wno-unused-parameter','-fsanitize=address,undefined',str(p/'credit-test.c'),'-o',str(p/'credit-test')],check=True);r=subprocess.run([str(p/'credit-test')],capture_output=True,text=True);assert r.returncode==0,r.stderr;(p/'credit-result.json').write_text(json.dumps({'passed':True,'summary':r.stdout.strip(),'ASan':True,'UBSan':True},indent=2)+'\n');print(r.stdout)
