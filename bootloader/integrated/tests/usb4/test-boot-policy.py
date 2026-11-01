from pathlib import Path
import subprocess,json
w=Path(__file__).resolve().parent
s=(w/'source/cmd/apple_atc_m1.c').read_text();f=s[s.index('static int do_tbboot('):s.index('U_BOOT_CMD(tbboot')]
c=r'''
#include <stdio.h>
#include <stdbool.h>
#include <string.h>
#include <assert.h>
#include <errno.h>
#define CMD_RET_USAGE 99
#define ATC_USB4 4
#define ATC_TBT 3
#define APPLE_NHI_BOOT_NONE 0
#define APPLE_NHI_BOOT_TB3 3
#define APPLE_NHI_BOOT_USB4 4
struct atc_m1_hw {struct {int mode;}cfg;};
struct apple_cd321x_status {int unused;};struct cmd_tbl{int unused;};
static int config_ret,selected,armed,calls,bootflow,resets,starts;
static int ofnode_path(const char*s){assert(!strcmp(s,"/soc/phy@503000000"));return 1;}
static int load_config(int n,struct atc_m1_hw*h,struct apple_cd321x_status*s){assert(n==1);calls++;h->cfg.mode=selected;return config_ret;}
static void apple_nhi_m1_set_boot_mode(int mode){armed=mode;}
static int run_command(const char*s,int flag){assert(!flag);if(!strcmp(s,"bootflow scan -lb")){bootflow++;assert(!starts&&!armed);}else{assert(!strcmp(s,"reset"));resets++;assert(starts==1&&!armed);}return 0;}
static int do_atcm1(struct cmd_tbl*c,int flag,int argc,char*const argv[]){assert(argc==3&&!strcmp(argv[0],"atcm1")&&!strcmp(argv[1],"1"));assert(armed==selected);assert(!strcmp(argv[2],selected==4?"usb4pciec":"tbtpciec"));starts++;return -EIO;}
'''+f+r'''
int main(void){unsigned n=0;for(int mode=3;mode<=4;mode++)for(int err=0;err<=6;err++){
 config_ret=err?-err:0;selected=mode;armed=calls=bootflow=resets=starts=0;
 assert(!do_tbboot(NULL,0,1,NULL));assert(calls==1&&!armed);
 if(err)assert(bootflow==1&&!starts&&!resets);else assert(!bootflow&&starts==1&&resets==1);n++;
 }calls=0;assert(do_tbboot(NULL,0,2,NULL)==99&&!calls);n++;printf("PASS %u actual boot policy cases\\n",n);}
'''
(w/'boot-policy.c').write_text(c)
subprocess.run(['cc','-Wall','-Wextra','-Wno-unused-parameter','-fsanitize=address,undefined','-o',str(w/'boot-policy'),str(w/'boot-policy.c')],check=True)
r=subprocess.run([str(w/'boot-policy')],capture_output=True,text=True);(w/'boot-policy.log').write_text(r.stdout+r.stderr);r.check_returncode();print(r.stdout.splitlines()[-1])
# Compile the actual exclusive transport dispatch with tracked failure injection.
s=(w/'source/cmd/apple_nhi_m1_ring.c').read_text();a=s.index('  if (!ret && boot_mode == APPLE_NHI_BOOT_USB4)');b=s.index('  } else if (boot_mode == APPLE_NHI_BOOT_NONE)',a)
f=s[a:b]+'  }\n'
names=['diagnostic_remote_read','apple_nhi_m1_usb4_router_setup','apple_nhi_m1_remote_inventory','apple_nhi_m1_usb4_preflight','diagnostic_usb4_credits','diagnostic_usb4_paths','apple_nhi_m1_remote_configure','diagnostic_path_snapshot','diagnostic_path_program','diagnostic_pcie_enable','apple_pciec_m1_scan','apple_pciec_m1_nvme_read']
c='#include <stdio.h>\n#include <assert.h>\ntypedef unsigned u32;\n#define APPLE_NHI_BOOT_USB4 4\n#define APPLE_NHI_BOOT_TB3 3\nstatic int boot_mode,count,fail,trace[30];\nstatic int step(int id){trace[count++]=id;return count==fail?-5:0;}\n'
for i,name in enumerate(names):c+=f'#define {name}(...) step({i})\n'
c+='static int run(int initial){struct {int last_response_port,usb4_snapshot;}ring;int ret=initial;\n'+f+'return ret;}\n'
c+=r'''int main(void){int expected[2][9]={{0,6,2,7,8,9,10,11,-1},{0,1,2,3,4,5,-1,-1,-1}};unsigned n=0;for(boot_mode=3;boot_mode<=4;boot_mode++){int total=boot_mode==3?8:6;for(fail=0;fail<=total;fail++){count=0;int ret=run(0);assert(ret==(fail?-5:0));assert(count==(fail?fail:total));for(int i=0;i<count;i++)assert(trace[i]==expected[boot_mode-3][i]);n++;}count=0;assert(run(-7)==-7&&!count);n++;}printf("PASS %u dispatch/stop-on-error cases\n",n);}
'''
(w/'dispatch.c').write_text(c);subprocess.run(['cc','-Wall','-Wextra','-fsanitize=address,undefined','-o',str(w/'dispatch'),str(w/'dispatch.c')],check=True)
r=subprocess.run([str(w/'dispatch')],capture_output=True,text=True);(w/'dispatch.log').write_text(r.stdout+r.stderr);r.check_returncode();print(r.stdout)
(w/'boot-policy-result.json').write_text(json.dumps({'actual_boot_policy_cases':15,'actual_exclusive_dispatch_cases':18,'passed':True,'asan':True,'ubsan':True},indent=2)+'\n')
