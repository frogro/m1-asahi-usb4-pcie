from pathlib import Path
import subprocess, sys
p=Path(__file__).parent;s=Path(sys.argv[1]);o=Path(sys.argv[2]);o.mkdir(exist_ok=True);(o/'linux').mkdir(exist_ok=True)
(o/'linux/types.h').write_text('#include <stdint.h>\n#include <stddef.h>\n#include <stdbool.h>\ntypedef uint64_t u64;\ntypedef uint32_t u32;\n')
(o/'apple_boot_media.h').write_bytes((s/'include/apple_boot_media.h').read_bytes())
(o/'linux/string.h').write_text('#include <string.h>\n')
body=(s/'cmd/apple_atc_m1.c').read_text();body=body[body.index('static int do_tbboot('):body.index('U_BOOT_CMD(tbboot,')]
pre=r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include <errno.h>
#include <apple_boot_media.h>
#define BIT(n) (1U<<(n))
#define CMD_RET_USAGE 2
#define CMD_RET_FAILURE 1
#define ATC_USB4 4
#define APPLE_NHI_BOOT_USB4 4
#define APPLE_NHI_BOOT_TB3 3
struct cmd_tbl {int unused;};
struct atc_m1_hw {struct {int mode;}cfg;};struct apple_cd321x_status {int unused;};
struct port {const char *phy;};static struct port ports[2]={{"p0"},{"p1"}};
static const char *uuid="82aaa9e7-2d28-412b-a0a8-52c39695445c";
static int hasmask,readfail,current,pre[2],startcount[2],failedport,booted,resets,scans;
static u32 mask;static const char *target;static int absent[2];
static const char *env_get(const char*n){(void)n;return NULL;}
static const char *ofnode_path(const char*n){return n;}
static const char *ofnode_read_string(const char*n,const char*k){(void)n;if(!strcmp(k,"u-boot,boot-partuuid"))return target;return NULL;}
static int ofnode_read_bool(const char*n,const char*k){(void)n;return !strcmp(k,"u-boot,boot-port-mask")?hasmask:!strcmp(k,"u-boot,auto-transport");}
static int ofnode_read_u32(const char*n,const char*k,u32*v){(void)n;(void)k;*v=mask;return readfail;}
static void apple_boot_test_record(void){}
static int apple_boot_scan_begin(void){scans++;return 0;}
static int apple_pciec_m1_boot_recovery(void){return -1;}
static int apple_boot_test_snapshot(void){return 0;}
static int apple_boot_reset(void){resets++;return 0;}
static int apple_boot_port_select(int p){assert(p==0||p==1);current=p;return 0;}
static struct port *apple_boot_port(void){return &ports[current];}
static int load_config(const char*n,struct atc_m1_hw*h,struct apple_cd321x_status*t){(void)n;(void)t;pre[current]++;h->cfg.mode=ATC_USB4;return absent[current]?-ENOTCONN:0;}
static int run_command(const char*n,int f){(void)n;(void)f;return 0;}
static void apple_nhi_m1_set_boot_mode(int m){(void)m;}
static int do_atcm1(struct cmd_tbl*c,int f,int n,char**a){(void)c;(void)f;(void)n;assert(a[1][0]=='0'+current);startcount[current]++;return current==failedport?1:0;}
static int apple_pciec_m1_inventory_active(void){return 1;}
static int apple_usb3_inventory_active(void){return 0;}
static int apple_pciec_m1_collect(struct apple_boot_media*m,size_t*n,size_t max){assert(*n<max);m+=(*n)++;m->transport=APPLE_BOOT_TRANSPORT_NVME;m->source=current;m->partition=6;m->efi_system_partition=m->has_efi_loader=true;strcpy(m->partuuid,uuid);return 0;}
static int apple_usb3_inventory_collect(struct apple_boot_media*m,size_t*n,size_t z){(void)m;(void)n;(void)z;abort();}
static int apple_usb3_boot_selected(const struct apple_boot_media*m){(void)m;abort();}
static int apple_pciec_m1_boot_selected(unsigned p){assert(p==6);booted++;return 0;}
'''
post=r'''
static void init(void){hasmask=1;readfail=0;mask=1;target=uuid;current=0;failedport=-1;booted=resets=scans=0;memset(pre,0,sizeof(pre));memset(startcount,0,sizeof(startcount));memset(absent,0,sizeof(absent));}
static int run(void){char*a[]={"tbboot"};return do_tbboot(NULL,0,1,a);}
int main(void){unsigned cases=0;
#define CHECK(x) do{assert(x);cases++;}while(0)
for(unsigned p=0;p<2;p++){init();mask=1U<<p;CHECK(!run());CHECK(booted==1&&pre[p]==1&&startcount[p]==1&&!pre[1-p]&&!startcount[1-p]);}
unsigned bad[]={0,4,5,0xffffffff};for(unsigned n=0;n<4;n++){init();mask=bad[n];CHECK(run()==CMD_RET_FAILURE);CHECK(!scans&&!pre[0]&&!pre[1]&&!booted);}
init();target=NULL;CHECK(run()==CMD_RET_FAILURE);CHECK(!scans&&!booted);
init();target="bad";CHECK(run()==CMD_RET_FAILURE);CHECK(!scans&&!booted);
init();readfail=-EINVAL;CHECK(run()==CMD_RET_FAILURE);CHECK(!scans&&!booted);
init();failedport=0;CHECK(!run());CHECK(!booted&&!pre[1]&&!startcount[1]&&resets==1);
init();absent[0]=1;CHECK(!run());CHECK(!booted&&!startcount[0]&&!pre[1]);
init();hasmask=0;CHECK(!run());CHECK(pre[0]&&pre[1]&&startcount[0]&&startcount[1]&&!booted); /* Duplicate UUID remains an error. */
struct apple_boot_source src[2]={{.state=APPLE_BOOT_SOURCE_EXCLUDED},{.state=APPLE_BOOT_SOURCE_COMPLETE}};
struct apple_boot_media m={.source=1,.transport=APPLE_BOOT_TRANSPORT_NVME,.partition=6,.efi_system_partition=1,.has_efi_loader=1};strcpy(m.partuuid,uuid);struct apple_boot_inventory inv={src,2,&m,1};size_t chosen;
CHECK(!apple_boot_media_select(&inv,uuid,&chosen)&&chosen==0);
CHECK(apple_boot_media_select(&inv,NULL,&chosen)==-EINVAL);
m.source=0;CHECK(apple_boot_media_select(&inv,uuid,&chosen)==-EINVAL);
m.source=1;src[0].error=-EIO;CHECK(apple_boot_media_select(&inv,uuid,&chosen)==-EINVAL);
printf("PASS %u actual boot-scope and selection safety checks\n",cases);}
'''
f=o/'scope.c';f.write_text(pre+body+post)
subprocess.run(['cc','-Wall','-Wextra','-Wno-unused-parameter','-Werror','-fsanitize=address,undefined','-I'+str(o),str(f),str(s/'lib/apple_boot_media.c'),'-o',str(o/'scope')],check=True)
r=subprocess.run([str(o/'scope')],capture_output=True,text=True);(o/'scope.log').write_text(r.stdout+r.stderr);r.check_returncode();print(r.stdout.splitlines()[-1])
