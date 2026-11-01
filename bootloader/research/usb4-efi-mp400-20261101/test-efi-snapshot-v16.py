from pathlib import Path
import subprocess,json
w=Path(__file__).resolve().parent;p=w/'efi-snapshot-tests';p.mkdir(exist_ok=True)
s=(w/'source/cmd/apple_pciec_m1.c').read_text();fn=s[s.index('static int usb4_efi_snapshot'):s.index('static int tb_boot_efi')]
(p/'actual.inc').write_text(fn)
c=r'''#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <assert.h>
typedef uint8_t u8;
#define SHA256_SUM_LEN 32
#define CHUNKSZ_SHA256 65536
#define CONFIG_CONSOLE_RECORD 1
#define IS_ENABLED(x) (x)
#define GD_FLG_RECORD 1
#define GD_FLG_RECORD_OVF 2
struct membuf {unsigned cursor;};
struct global_data {unsigned flags;struct membuf console_out;} data,*gd=&data;
static int enabled=1,available,envfail,shortread;static unsigned envcalls;
static int ofnode_path(const char*s){return 1;}
static int ofnode_read_bool(int n,const char*s){return enabled;}
static void sha256_csum_wd(const void*p,int n,u8*d,unsigned c){memset(d,0,32);}
static int console_record_avail(void){return available;}
static int membuf_get(struct membuf*b,char*p,int n){memset(p,'a',n);b->cursor+=n;return n-shortread;}
static int env_set(const char*k,const char*v){envcalls++;assert(strlen(v)==(unsigned)available);return envfail;}
#include "actual.inc"
static void init(void){enabled=1;available=100;envfail=shortread=0;envcalls=0;data.flags=GD_FLG_RECORD;data.console_out.cursor=17;}
int main(void){unsigned n=0;char image[4]={0};
init();assert(!usb4_efi_snapshot(image,4)&&envcalls==1&&data.console_out.cursor==17);n++;
init();enabled=0;assert(!usb4_efi_snapshot(image,4)&&!envcalls);n++;
for(int size=0;size>=-1;size--){init();assert(usb4_efi_snapshot(image,size)==-EOVERFLOW&&!envcalls);n++;}
for(unsigned flags=0;flags<=3;flags++){if(flags==1)continue;init();data.flags=flags;assert(usb4_efi_snapshot(image,4)==-EOVERFLOW&&!envcalls);n++;}
int sizes[]={0,-1,65537};for(unsigned i=0;i<3;i++){init();available=sizes[i];assert(usb4_efi_snapshot(image,4)==-EOVERFLOW&&!envcalls);n++;}
init();available=65536;assert(!usb4_efi_snapshot(image,4)&&data.console_out.cursor==17);n++;
init();shortread=1;assert(usb4_efi_snapshot(image,4)==-EIO&&!envcalls&&data.console_out.cursor==17);n++;
init();envfail=-ENOMEM;assert(usb4_efi_snapshot(image,4)==-ENOMEM&&data.console_out.cursor==17);n++;
printf("CASES %u PASS; bounded snapshot preserves original recording ring\n",n);}
'''
(p/'test.c').write_text(c)
subprocess.run(['cc','-Wall','-Wextra','-Wno-unused-parameter','-fsanitize=address,undefined',str(p/'test.c'),'-o',str(p/'test')],check=True)
r=subprocess.run([str(p/'test')],capture_output=True,text=True);(p/'test.log').write_text(r.stdout+r.stderr);assert r.returncode==0,r.stderr
result={'passed':True,'summary':r.stdout.splitlines()[-1],'ASan':True,'UBSan':True};(p/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(result)
