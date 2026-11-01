from pathlib import Path
import subprocess,json,sys
source=Path(sys.argv[1]).resolve();w=Path(sys.argv[2]).resolve();w.mkdir(parents=True,exist_ok=False)
s=(source/'cmd/apple_atc_m1.c').read_text();a=s.index('int apple_atc_m1_quiesce(');b=s.index('static void show_stage',a);helper=s[a:b]
s=(source/'cmd/apple_pciec_m1.c').read_text();a=s.index('static int tb_stop_for_efi(');b=s.index('static void EFIAPI tb_efi_exit_notify',a);handover=s[a:b]
c=r'''#include <stdio.h>
#include <stdbool.h>
#include <errno.h>
#include <assert.h>
#define CONFIG_IS_ENABLED(x) 1
#define DM_REMOVE_NORMAL 1
struct xhci_ctrl{int x;};static struct xhci_ctrl controller,*boot_xhci;
static unsigned step,fail,halting;static int trace[16];
static int op(int n){trace[step++]=n;return step==fail?-EIO:0;}
static int xhci_m1_diag_stop(struct xhci_ctrl*c){assert(c==&controller);halting++;return op(2);}
'''+helper+r'''
static struct{bool live,dma;int dart;}tb;static bool tb_efi_exit_done,tb_efi_check_dart;
static int tb_quiesce(void){return op(1);}
static int apple_nhi_m1_quiesce(void){return op(3);}
static int apple_acio_m1_prepare_os(void){return op(4);}
static int apple_nhi_m1_remove_dart(void){return op(5);}
static int device_remove(int d,int flags){assert(d==7&&flags==1);return op(6);}
'''+handover+r'''
static void init(bool retained){step=halting=0;boot_xhci=retained?&controller:NULL;tb.live=tb.dma=tb_efi_exit_done=false;tb.dart=7;tb_efi_check_dart=true;}
int main(void){unsigned n=0;
for(int retained=0;retained<2;retained++){unsigned total=retained?6:5;for(fail=0;fail<=total;fail++){init(retained);int ret=tb_stop_for_efi();assert(ret==(fail?-EIO:0));assert(step==(fail?fail:total));assert(tb_efi_exit_done==!fail);for(unsigned i=0;i<step;i++)assert(trace[i]==(int)(i+1+(retained||!i?0:1)));if(!fail){unsigned saved=step;assert(!tb_stop_for_efi()&&step==saved&&!boot_xhci);}n++;}}
fail=0;init(true);tb.live=true;assert(tb_stop_for_efi()==-EBUSY&&step==1&&boot_xhci);n++;
init(true);tb.dma=true;assert(tb_stop_for_efi()==-EBUSY&&step==1&&boot_xhci);n++;
init(true);fail=1;assert(apple_atc_m1_quiesce()==-EIO&&boot_xhci);n++;
fail=0;assert(!apple_atc_m1_quiesce()&&!boot_xhci);unsigned saved=step;assert(!apple_atc_m1_quiesce()&&step==saved);n++;
printf("PASS %u actual xHCI/EFI handover cases; ordered halt and failure barriers\n",n);}
'''
(w/'xhci-handover.c').write_text(c);subprocess.run(['cc','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',str(w/'xhci-handover.c'),'-o',str(w/'xhci-handover')],check=True)
p=subprocess.run([str(w/'xhci-handover')],capture_output=True,text=True);(w/'xhci-handover.log').write_text(p.stdout+p.stderr);p.check_returncode();print(p.stdout.splitlines()[-1]);(w/'xhci-handover-result.json').write_text(json.dumps({'passed':True,'summary':p.stdout.splitlines()[-1],'ASan':True,'UBSan':True},indent=2)+'\n')
