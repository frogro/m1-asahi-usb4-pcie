from pathlib import Path
import subprocess as s,os,sys
here=Path(__file__).resolve().parent;src=Path(sys.argv[1]).resolve();w=Path(sys.argv[2]).resolve();w.mkdir(parents=True,exist_ok=True);old=here/'tests'
t=(src/'cmd/apple_atc_m1.c').read_text();actual=t[t.index('static int do_tbboot('):t.index('\nU_BOOT_CMD(tbboot')]
pre=r'''
#include <apple_boot_media.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <assert.h>
struct cmd_tbl {int unused;};
struct atc_m1_hw {struct {int mode;}cfg;};
struct apple_cd321x_status {int unused;};
struct port {unsigned int index; const char *phy;};
static struct port ports[2]={{0,"port0"},{1,"port1"}};
static unsigned selected,checked,started,collected,booted,bootport,resets,scans;
static int eligibility[2],start_error[2],collect_error[2],present[2],duplicate;
static const char *target, *preferred, *local_bootcmd, *recovery;
static unsigned recoveries;
static int common_menu,inventory_test,usb_port=-1,automatic,both_protocols;
static bool apple_pciec_m1_inventory_active(void){return both_protocols||(int)selected!=usb_port;}
static int recovery_error;
static const char *uuid[2]={"3637d5db-02a2-46f6-892c-56e6e17c84c9","a2b3c4d5-e6f7-489a-b012-3456789abcde"};
#define CMD_RET_USAGE 2
#define CMD_RET_FAILURE 1
#define ATC_USB4 4
#define APPLE_NHI_BOOT_USB4 4
#define APPLE_NHI_BOOT_TB3 3
static const char *env_get(const char*n){(void)n;return target;}
static const char *ofnode_read_string(const char*n,const char*k){(void)n;if(!strcmp(k,"u-boot,preferred-partuuid"))return preferred;if(!strcmp(k,"u-boot,local-bootcmd"))return local_bootcmd;if(!strcmp(k,"u-boot,recovery-partuuid"))return recovery;return NULL;}
static bool ofnode_read_bool(const char*n,const char*k){(void)n;return (!strcmp(k,"u-boot,common-menu")&&common_menu)||(!strcmp(k,"u-boot,usb3-inventory-test")&&inventory_test)||(!strcmp(k,"u-boot,auto-transport")&&automatic);}
static bool apple_usb3_inventory_active(void){return (int)selected==usb_port;}
static const char *ofnode_path(const char*n){return n;}
static const struct port *apple_boot_port(void){return &ports[selected];}
static int apple_boot_port_select(unsigned p){assert(p<2);selected=p;return 0;}
static int apple_boot_scan_begin(void){return 0;}
static void apple_boot_test_record(void){}
static int apple_boot_test_snapshot(void){return 0;}
static int load_config(const char*p,struct atc_m1_hw*h,struct apple_cd321x_status*d){(void)p;(void)d;assert(!started);checked|=1U<<selected;h->cfg.mode=4;return eligibility[selected];}
static void apple_nhi_m1_set_boot_mode(int m){assert(m==4);}
static int do_atcm1(struct cmd_tbl*c,int f,int ac,char**av){(void)c;(void)f;assert(ac==3&&av[1][0]=='0'+selected);assert(checked==3);started|=1U<<selected;return start_error[selected];}
static int apple_pciec_m1_collect(struct apple_boot_media*m,size_t*n,size_t cap){assert(started&(1U<<selected));collected|=1U<<selected;if(collect_error[selected])return collect_error[selected];if(!present[selected])return 0;assert(*n<cap);m[*n]=(struct apple_boot_media){.source=selected,.device=3+selected,.partition=1,.efi_system_partition=1,.has_efi_loader=1};strcpy(m[*n].partuuid,uuid[(duplicate||both_protocols)?0:selected]);(*n)++;return 0;}
static int apple_usb3_inventory_collect(struct apple_boot_media*m,size_t*n,size_t cap){int r=apple_pciec_m1_collect(m,n,cap);if(!r&&*n){m[*n-1].transport=APPLE_BOOT_TRANSPORT_USB;if(both_protocols&&!duplicate)strcpy(m[*n-1].partuuid,uuid[1]);}return r;}
static int apple_pciec_m1_boot_selected(unsigned p){assert(p==1);unsigned needed=0;for(unsigned i=0;i<2;i++)if(!eligibility[i])needed|=1U<<i;assert(collected==needed);booted++;bootport=selected;return -999;}
static int apple_usb3_boot_selected(const struct apple_boot_media*m){assert(m->source==selected&&m->transport==APPLE_BOOT_TRANSPORT_USB&&m->partition==1);booted++;bootport=selected;return -999;}
static int apple_pciec_m1_boot_recovery(void){unsigned needed=0;for(unsigned i=0;i<2;i++)if(!eligibility[i])needed|=1U<<i;assert(collected==needed);assert(recovery&&!target);recoveries++;return recovery_error;}
static int apple_boot_reset(void){resets++;return 0;}
static int run_command(const char*c,int f){(void)f;assert(!strcmp(c,local_bootcmd?local_bootcmd:"bootflow scan -lb"));assert(!started);scans++;return 0;}
'''
post=r'''
static void init(void){common_menu=both_protocols=automatic=0;inventory_test=0;usb_port=-1;selected=checked=started=collected=booted=bootport=resets=scans=duplicate=0;for(int i=0;i<2;i++){eligibility[i]=start_error[i]=collect_error[i]=0;present[i]=1;}target=preferred=local_bootcmd=recovery=NULL;recoveries=0;recovery_error=-999;}
static void run(void){assert(do_tbboot(NULL,0,1,NULL)==0);}
int main(void){unsigned cases=0;
 char *badargs[]={"tbboot","bad"}; char *recoveryargs[]={"tbboot","recovery"};
 init();assert(do_tbboot(NULL,0,2,badargs)==2);assert(!checked);cases++;
 init();target="bad";assert(do_tbboot(NULL,0,1,NULL)==1);assert(!checked);cases++;
 init();eligibility[0]=-ENOTCONN;eligibility[1]=-EPROTONOSUPPORT;run();assert(scans==1&&!booted&&resets==1);cases++;
 init();eligibility[0]=eligibility[1]=-ENOTCONN;target=uuid[0];run();assert(!scans&&!booted&&resets==1);cases++;
 for(int p=0;p<2;p++){init();eligibility[1-p]=-ENOTCONN;target=uuid[p];run();assert(booted==1&&bootport==(unsigned)p);cases++;}
 for(int p=0;p<2;p++){init();target=uuid[p];run();assert(collected==3&&booted==1&&bootport==(unsigned)p);cases++;}
 init();run();assert(collected==3&&!booted&&resets==1);cases++;
 init();duplicate=1;target=uuid[0];run();assert(!booted&&collected==3);cases++;
 for(int p=0;p<2;p++){init();eligibility[p]=-EIO;run();assert(!started&&!booted&&resets==1);cases++;}
 for(int p=0;p<2;p++){init();collect_error[p]=-EIO;target=uuid[1-p];run();assert(!booted&&resets==1);cases++;}
 for(int p=0;p<2;p++){init();start_error[p]=1;target=uuid[1-p];run();assert(!booted&&resets==1);cases++;}
 for(int p=0;p<2;p++){init();present[p]=0;run();assert(booted==1&&bootport==(unsigned)(1-p));cases++;}
 init();preferred=uuid[0];eligibility[0]=eligibility[1]=-ENOTCONN;run();assert(scans==1&&!started&&resets==1);cases++;
 init();preferred=uuid[0];local_bootcmd="configured local EFI";eligibility[0]=-ENOTCONN;eligibility[1]=-EPROTONOSUPPORT;run();assert(scans==1&&!started&&resets==1);cases++;
 for(int p=0;p<2;p++){init();preferred=uuid[p];run();assert(booted==1&&bootport==(unsigned)p&&collected==3);cases++;}
 init();preferred=uuid[0];target=uuid[1];run();assert(booted==1&&bootport==1);cases++;
 init();preferred=uuid[0];present[0]=0;run();assert(!booted&&!scans&&resets==1);cases++;
 init();preferred="bad";assert(do_tbboot(NULL,0,1,NULL)==1);assert(!checked&&!started);cases++;
 init();preferred=uuid[0];local_bootcmd="configured local EFI";eligibility[0]=-EIO;run();assert(!scans&&!started&&resets==1);cases++;
 init();target=uuid[0];local_bootcmd="configured local EFI";eligibility[0]=eligibility[1]=-ENOTCONN;run();assert(!scans&&!booted&&resets==1);cases++;
 for(int p=0;p<2;p++){init();preferred=uuid[p];present[p]=0;recovery=uuid[1];run();assert(recoveries==1&&!booted&&resets==1&&collected==3);cases++;}
 init();preferred=uuid[0];present[0]=present[1]=0;recovery=uuid[1];run();assert(recoveries==1&&!booted);cases++;
 init();preferred=uuid[0];target=uuid[0];present[0]=0;recovery=uuid[1];run();assert(!recoveries&&!booted&&resets==1);cases++;
 init();preferred=uuid[0];recovery=uuid[1];duplicate=1;run();assert(!recoveries&&!booted&&resets==1);cases++;
 init();preferred=uuid[0];recovery=uuid[1];collect_error[0]=-EIO;run();assert(!recoveries&&!booted&&resets==1);cases++;
 init();preferred=uuid[0];recovery=uuid[1];eligibility[0]=-EIO;run();assert(!recoveries&&!started&&resets==1);cases++;
 init();preferred=uuid[0];recovery=uuid[1];present[0]=0;recovery_error=-EIO;run();assert(recoveries==1&&!booted&&resets==1);cases++;
 init();preferred=uuid[0];recovery=uuid[1];eligibility[0]=eligibility[1]=-ENOTCONN;run();assert(scans==1&&!recoveries&&!booted);cases++;
 for(int err=0;err<2;err++){init();recovery=uuid[0];recovery_error=err?-EIO:0;eligibility[0]=eligibility[1]=-EIO;assert(do_tbboot(NULL,0,2,recoveryargs)==0);assert(recoveries==1&&!checked&&!started&&!collected&&resets==1);cases++;}
 for(int p=0;p<2;p++){init();inventory_test=1;usb_port=p;target=uuid[p];run();assert(!booted&&!recoveries&&resets==1&&collected==3);cases++;}
 init();inventory_test=1;usb_port=1;preferred=uuid[1];present[1]=0;recovery=uuid[0];run();assert(!booted&&!recoveries&&resets==1);cases++;
 for(int p=0;p<2;p++){init();usb_port=p;target=uuid[p];run();assert(booted==1&&bootport==(unsigned)p&&!recoveries&&collected==3&&resets==1);cases++;}
 init();inventory_test=1;usb_port=1;collect_error[1]=-EIO;target=uuid[0];run();assert(!booted&&!recoveries&&resets==1);cases++;
for(int p=0;p<2;p++){init();automatic=1;usb_port=p;target=uuid[p];run();assert(booted==1&&bootport==(unsigned)p&&collected==3);cases++;}
 init();automatic=1;usb_port=1;target=uuid[0];run();assert(booted==1&&bootport==0&&collected==3);cases++;
 init();automatic=1;usb_port=1;collect_error[1]=-EIO;target=uuid[0];run();assert(!booted&&resets==1);cases++;
 for(int p=0;p<2;p++)for(int targetidx=0;targetidx<2;targetidx++){init();automatic=both_protocols=1;usb_port=p;eligibility[1-p]=-ENOTCONN;target=uuid[targetidx];run();assert(booted==1&&bootport==(unsigned)p&&collected==(1U<<p));cases++;}
 init();automatic=both_protocols=duplicate=1;usb_port=1;eligibility[0]=-ENOTCONN;target=uuid[0];run();assert(!booted&&resets==1);cases++;

 /* Common menu: zero, one, or multiple external candidates never choose OS. */
 for(int mask=0;mask<4;mask++)for(int err=0;err<2;err++){
  init();common_menu=1;recovery=uuid[0];present[0]=mask&1;present[1]=mask&2;
  recovery_error=err?-EIO:0;run();assert(recoveries==1&&!booted&&collected==3&&resets==1);cases++;
 }
 for(int p=0;p<2;p++){
  init();common_menu=automatic=1;recovery=uuid[0];usb_port=p;run();assert(recoveries==1&&!booted&&collected==3);cases++;
  init();common_menu=1;recovery=uuid[0];eligibility[p]=-EIO;run();assert(!recoveries&&!booted&&!started);cases++;
  init();common_menu=1;recovery=uuid[0];collect_error[p]=-EIO;run();assert(!recoveries&&!booted);cases++;
  init();common_menu=1;recovery=uuid[0];start_error[p]=-EIO;run();assert(!recoveries&&!booted);cases++;
 }
 init();common_menu=1;recovery=uuid[0];eligibility[0]=eligibility[1]=-ENOTCONN;run();assert(scans==1&&!recoveries&&!booted);cases++;
 init();common_menu=1;recovery=uuid[0];target=uuid[1];assert(do_tbboot(NULL,0,1,NULL)==1);assert(!checked&&!recoveries);cases++;
 init();common_menu=1;assert(do_tbboot(NULL,0,1,NULL)==1);assert(!checked&&!recoveries);cases++;
 init();common_menu=1;recovery="bad";assert(do_tbboot(NULL,0,1,NULL)==1);assert(!checked&&!recoveries);cases++;
 init();common_menu=inventory_test=1;recovery=uuid[0];assert(do_tbboot(NULL,0,1,NULL)==1);assert(!checked&&!recoveries);cases++;
  printf("PASS: %u actual two-controller orchestration cases\n", cases);return 0;}
'''
p=w/'scan-actual.c';p.write_text(pre+actual+post);env=os.environ.copy();env['TMPDIR']=str(w)
s.run(['cc','-g','-O1','-fsanitize=address,undefined','-I'+str(old/'include'),str(p),str(src/'lib/apple_boot_media.c'),'-o',str(w/'scan-actual')],check=True,env=env)
with (w/'scan-results.log').open('w') as f:s.run([str(w/'scan-actual')],check=True,stdout=f,stderr=f,env=env)
print((w/'scan-results.log').read_text().splitlines()[-1])
