from pathlib import Path
import subprocess,json,sys
r=Path(sys.argv[3]).resolve();r.mkdir(parents=True,exist_ok=True)
fixture=Path(sys.argv[2]).resolve()
s=(Path(sys.argv[1])/'cmd/apple_pciec_m1.c').read_text()
def function(name):
 a=s.index('static int '+name+'(');a=s.index('static int '+name+'(',a+1) if s[s.index(')',a)+1:s.index(')',a)+3].startswith(';') else a
 start=s.index('{',a);depth=1;i=start+1
 while depth:
  depth+=(s[i]=='{')-(s[i]=='}');i+=1
 return s[a:i]
def run(name,code,extra=[]):
 code=code.replace('FIXTURE_PATH',json.dumps(str(fixture)))
 (r/(name+'.c')).write_text(code)
 subprocess.run(['cc','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-g','-o',str(r/name),str(r/(name+'.c')),*extra],check=True)
 p=subprocess.run([str(r/name)],capture_output=True,text=True);(r/(name+'.log')).write_text(p.stdout+p.stderr);print(p.stdout+p.stderr);p.check_returncode()
run('efi-read-test',r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <stdint.h>
#define ALIGN(x,a) (((x)+(a)-1)&~((a)-1))
static int fault,opens,closes,allocs,frees;
static void *allocation;
static int tb_fs_open(unsigned p){if(p!=7)abort();opens++;return (fault==1&&opens==1)||(fault==5&&opens==2)?-19:0;}
static int fs_size(const char *p,loff_t *size){if(strcmp(p,"/EFI/BOOT/BOOTAA64.EFI"))abort();*size=fault==3?511:fault==8?128*1024*1024+1:4097;return fault==2?-2:0;}
static void fs_close(void){closes++;}
static void *memalign(size_t a,size_t n){if(a!=4096||n!=8192)abort();allocs++;if(fault==4)return NULL;return allocation=malloc(n);}
static int fs_read(const char *p,unsigned long dst,loff_t off,loff_t n,loff_t *actual){if(strcmp(p,"/EFI/BOOT/BOOTAA64.EFI")||off||n!=4097||dst!=(unsigned long)allocation)abort();*actual=fault==7?n-1:n;return fault==6?-5:0;}
static void checked_free(void *p){if(p!=allocation)abort();frees++;free(p);allocation=NULL;}
#define free checked_free
'''+function('tb_read_efi')+r'''
#undef free
int main(void){for(fault=0;fault<=8;fault++){
 opens=closes=allocs=frees=0;allocation=NULL;void *image=(void *)1;int len=-1;
 int ret=tb_read_efi(7,&image,&len);
 if(!fault){if(ret||image!=allocation||len!=4097||closes!=2||frees)return 1;free(image);}
 else {if(!ret||image||len||allocation)return 2;
 if(closes!=(fault==1?0:(fault==6||fault==7?2:1)))return 3;
 if(frees!=(fault>=5&&fault<=7?1:0))return 4;}}
 puts("PASS 9 actual EFI read cases: arbitrary partition/size, failures, short read, cleanup");}
''')
run('efi-selection-test',r'''
#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
#define CONFIG_EFI_PARTITION_ENTRIES_NUMBERS 128
#define PART_EFI_SYSTEM_PARTITION 2
struct blk_desc {int devnum;};
struct disk_partition {int bootable; char uuid[8];};
static int scenario, reads, selected;
static int part_get_info(struct blk_desc *d,unsigned p,struct disk_partition *part){
 if(d->devnum!=9)abort();
 if(scenario==0)return -2;
 if(p!=3&&p!=7)return -2;
 part->bootable=(scenario==1||p==7)?2:0;part->uuid[0]=0;return 0;}
static int tb_read_efi(unsigned p,void **image,int *len){reads++;selected=p;
 if(scenario==1&&p==3)return -ENOENT;
 if(scenario==3)return -EIO;
 *image=(void *)0x1000;*len=4097;return 0;}
'''+function('tb_find_efi')+r'''
int main(void){struct blk_desc d={9};for(scenario=0;scenario<4;scenario++){
 void *image=(void *)1;int len=-1;reads=selected=0;
 int ret=tb_find_efi(&d,&image,&len);
 if(scenario==0){if(ret!=-ENOENT||image||len||reads)return 1;}
 else if(scenario==3){if(ret!=-EIO||image||len||reads!=1)return 2;}
 else {if(ret||selected!=7||len!=4097||image!=(void *)0x1000||reads!=(scenario==1?2:1))return 3;}}
 puts("PASS 4 actual GPT selection cases: gaps, no ESP, missing EFI, read failure");}
''')
# Real libfdt exercises the exact handover code, including a second EFI fixup.
run('handover-test',r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <libfdt.h>
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
'''+function('tb_linux_fdt')+r'''
int main(void){
 void *source=malloc(2097152),*dest=malloc(2097152);FILE *f=fopen(FIXTURE_PATH,"rb");if(!f)return 1;
 if(!fread(source,1,2097152,f))return 2;
 fclose(f);
 if(tb_linux_fdt(dest,source,2097152))return 3;
 const char *paths[]={"/soc/cio@381ac0000","/soc/usb4-pcie-tunnel-0","/soc/usb@382280000","/soc/cio@501ac0000"};
 for(unsigned i=0;i<ARRAY_SIZE(paths);i++) {const char *status=fdt_getprop(dest,fdt_path_offset(dest,paths[i]),"status",NULL);if(!status||strcmp(status,"okay"))return 4;}
 if(fdt_path_offset(dest,"/soc/pcie@530000000")!=-FDT_ERR_NOTFOUND)return 5;
 if(tb_linux_fdt(dest,dest,fdt_totalsize(dest)))return 6;
 if(tb_linux_fdt(dest,source,1)!=-EINVAL)return 7;
 fdt_delprop(source,fdt_path_offset(source,"/config"),"u-boot,tb-linux-tree");
 if(tb_linux_fdt(dest,source,2097152)!=-EPERM)return 8;
 free(source);free(dest);puts("PASS actual FDT: both native ports, duplicate removal, idempotent EFI fixup, size and marker guards");}
''',['-lfdt'])
(r/'integration-tests.json').write_text(json.dumps({'passed':True,'efi_read_cases':9,'efi_selection_cases':4,'actual_fdt_handover':True,'sanitizers':'ASan+UBSan'},indent=2)+'\n')
