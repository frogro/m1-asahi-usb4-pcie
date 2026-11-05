from pathlib import Path
import subprocess,json
import sys
w=Path(__file__).resolve().parent;s=Path(sys.argv[1])/'drivers/gpu/drm/apple'
a=(s/'afk.c').read_text();h=(s/'afk.h').read_text();d=(s/'dptxep.c').read_text()
def fn(t,name):
 start=t.index(name);start=t.rfind('\n',0,start)+1;op=t.index('{',start);depth=1;i=op+1
 while depth:
  depth+=(t[i]=='{')-(t[i]=='}');i+=1
 return t[start:i]+'\n'
pre=r'''
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
#include <errno.h>
typedef uint8_t u8;typedef uint16_t u16;typedef uint32_t u32;typedef uint16_t __le16;typedef uint32_t __le32;
#define cpu_to_le16(x) (x)
#define cpu_to_le32(x) (x)
#define le16_to_cpu(x) (x)
#define le32_to_cpu(x) (x)
#define MSEC_PER_SEC 1000
#define GFP_KERNEL 0
#define max(a,b) ((a)>(b)?(a):(b))
#define kzalloc(n,f) calloc(1,n)
#define kfree(p) free(p)
#define dev_info(...) ((void)0)
#define EPIC_SUBTYPE_STD_SERVICE 0
struct apple_epic_service {int unused;};
'''
pre+=h[h.index('struct epic_service_call {'):h.index('static_assert(sizeof(struct epic_service_call)')]
pre+=d[d.index('struct dcpdptx_hotplug_cmd {'):d.index('struct dptxport_apcall_link_rate')]
pre+=r'''
static unsigned int delay_ms,observed_ms;static int fault,calls;
static int afk_send_command_len(struct apple_epic_service *s,u8 type,const void *input,size_t inlen,void *output,size_t outlen,u32 *retcode,size_t *received,unsigned int timeout_ms){
 (void)s;(void)type;assert(input==output&&inlen==outlen);calls++;observed_ms=timeout_ms;
 if(delay_ms>timeout_ms)return -ETIMEDOUT;
 struct epic_service_call *c=output;*retcode=0;*received=outlen;
 if(fault==1)*received=sizeof(*c)-1;
 if(fault==2)*received=outlen+1;
 if(fault==3)c->data_len=0;
 if(fault==4)c->magic=0;
 if(fault==5)*retcode=1;
 if(fault==6)((struct dcpdptx_hotplug_cmd *)(c+1))->unk=99;
 return 0;
}
'''
body=fn(a,'static int afk_service_call_common(')+fn(a,'int afk_service_call_checked_timeout(')+fn(a,'int afk_service_call_checked(')+fn(a,'int afk_service_call(')+fn(d,'int dptxport_set_hpd_timeout(')+fn(d,'int dptxport_set_hpd(')
cases=r'''
int main(void){struct apple_epic_service s={0};int count=0;char dummy=0;
 delay_ms=3000;assert(dptxport_set_hpd(&s,false)==-ETIMEDOUT&&observed_ms==1000);count++;
 assert(!dptxport_set_hpd_timeout(&s,false,5000)&&observed_ms==5000);count++;
 delay_ms=5001;assert(dptxport_set_hpd_timeout(&s,false,5000)==-ETIMEDOUT);count++;
 delay_ms=0;assert(!dptxport_set_hpd(&s,true)&&observed_ms==1000);count++;
 int before=calls;assert(dptxport_set_hpd_timeout(&s,false,0)==-EINVAL);assert(dptxport_set_hpd_timeout(&s,false,5001)==-EINVAL);assert(calls==before);count+=2;
 for(fault=1;fault<=6;fault++){assert(dptxport_set_hpd_timeout(&s,false,5000)<0);count++;}
 fault=0;assert(!afk_service_call(&s,1,1,&dummy,0,0,NULL,0,0)&&observed_ms==1000);count++;
 assert(!afk_service_call_checked(&s,1,1,&dummy,0,0,NULL,0,0)&&observed_ms==1000);count++;
 printf("PASS: %d deadline/envelope cases from actual call stack; mocked transport timing; ASan/UBSan\n",count);return 0;}
'''
p=w/'withdraw-transport-test.c';p.write_text(pre+body+cases)
subprocess.run(['gcc','-std=gnu11','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all','-O1','-g',str(p),'-o',str(w/'withdraw-transport-test')],check=True)
r=subprocess.run([str(w/'withdraw-transport-test')],text=True,capture_output=True);print(r.stdout+r.stderr,end='');r.check_returncode();(w/'withdraw-transport-result.json').write_text(json.dumps({'result':r.stdout.strip(),'hardware':False},indent=2)+'\n')
