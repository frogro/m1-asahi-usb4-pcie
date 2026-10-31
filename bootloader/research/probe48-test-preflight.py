from pathlib import Path
import subprocess,shutil,json,hashlib
r=Path(__file__).parent;s=Path('/tmp/asahi-universal-boot-20261031/phy-candidate/source')
h=r/'host-include';shutil.copytree(r.parent/'pciec-preparation-probe45/host-include',h)
p=h/'linux/types.h';p.write_text(p.read_text()+'typedef uint64_t u64; typedef uint8_t u8;\n')
p=h/'linux/errno.h';p.write_text(p.read_text()+'#define EALREADY 114\n')
source=(s/'cmd/apple_pciec_m1.c').read_text();body=source[source.index('#define NODE'):source.index('static int hw_read')]
(r/'actual-preflight.inc').write_text(body)
pre=r'''#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <libfdt.h>
#include <apple_pciec_m1.h>
#include <linux/errno.h>
static unsigned char dt[131072], initial[131072];
static unsigned int maps, cases;
typedef int ofnode;
struct resource {u64 start,end;};
static ofnode ofnode_path(const char *n){return fdt_path_offset(dt,n);}
static ofnode ofnode_root(void){return 0;}
static bool ofnode_valid(ofnode n){return n>=0;}
static bool ofnode_device_is_compatible(ofnode n,const char *c){return n>=0 && !fdt_node_check_compatible(dt,n,c);}
static bool ofnode_is_enabled(ofnode n){int len;const char *p=fdt_getprop(dt,n,"status",&len);return !p || !strcmp(p,"okay") || !strcmp(p,"ok");}
static const void *ofnode_get_property(ofnode n,const char *p,int *l){return fdt_getprop(dt,n,p,l);}
static u32 get_unaligned_be32(const void *p){u32 v;memcpy(&v,p,4);return fdt32_to_cpu(v);}
static int ofnode_read_resource_byname(ofnode n,const char *name,struct resource *r){
 int idx=fdt_stringlist_search(dt,n,"reg-names",name),len;const fdt32_t *v=fdt_getprop(dt,n,"reg",&len);
 if(idx<0||!v||len<(idx+1)*16)return -EINVAL;
 v+=4*idx;r->start=((u64)fdt32_to_cpu(v[0])<<32)|fdt32_to_cpu(v[1]);
 r->end=r->start+(((u64)fdt32_to_cpu(v[2])<<32)|fdt32_to_cpu(v[3]))-1;return 0;
}
static u64 resource_size(const struct resource *r){return r->end-r->start+1;}
static void *map_sysmem(u64 a,u32 sz){maps++;return (void *)(uintptr_t)a;}
'''
post=r'''
static void reset(void){memcpy(dt,initial,sizeof(dt));maps=0;used=false;checked=false;}
static void setgroup(unsigned g,bool native,int kind){
 fdt32_t data[PCIEC_M1_MAX_TUNABLES*6];unsigned count,i;const struct pciec_m1_tunable *ref=pciec_m1_reference(g,&count);
 for(i=0;i<count;i++){data[i*3]=cpu_to_fdt32(ref[i].offset);data[i*3+1]=cpu_to_fdt32(ref[i].mask);data[i*3+2]=cpu_to_fdt32(ref[i].value);}
 if(kind==1)data[0]^=cpu_to_fdt32(1);
 if(kind==2)memcpy(data+count*3,data,count*12);
 int n=ofnode_path(native?(g==PCIEC_PORT?NODE "/pci@0,0":NODE):"/config");
 if(fdt_setprop(dt,n,native?props[g]:reference_props[g],data,count*12*(kind==2?2:1)))abort();
}
static void defaults(bool native){for(unsigned g=0;g<5;g++)setgroup(g,native,0);}
static void expect(const char *label,int want){int got=apple_pciec_m1_check();cases++;
 if(got!=want||maps!=(want?0:5)||checked!=(want==0)){fprintf(stderr,"FAIL %s got=%d expected=%d maps=%u checked=%u\n",label,got,want,maps,checked);exit(1);}
 printf("PREFLIGHT-CASE PASS %s\n",label);
}
int main(int argc,char **argv){FILE *f=fopen(argv[1],"rb");if(!f)return 1;size_t size=fread(initial,1,sizeof(initial),f);fclose(f);if(!size||fdt_open_into(initial,dt,sizeof(dt)))return 1;memcpy(initial,dt,sizeof(dt));
 reset();defaults(true);expect("all generated",0);
 reset();defaults(false);expect("all saved reference",0);
 reset();defaults(false);for(unsigned g=0;g<3;g++)setgroup(g,true,0);expect("observed generated three plus saved two",0);
 reset();expect("both missing",-EINVAL);
 for(unsigned g=0;g<5;g++){
  reset();defaults(false);setgroup(g,true,1);expect("bad generated cannot use good fallback",-EINVAL);
  reset();defaults(false);setgroup(g,true,2);expect("doubled generated cannot use good fallback",-EINVAL);
  reset();defaults(false);setgroup(g,false,1);expect("bad saved reference rejected",-EINVAL);
  reset();defaults(false);setgroup(g,false,2);expect("doubled saved reference rejected",-EINVAL);
  reset();defaults(false);if(fdt_delprop(dt,ofnode_path("/config"),reference_props[g]))abort();expect("both sources missing for group",-EINVAL);
 }
 reset();defaults(false);if(fdt_setprop_string(dt,ofnode_path(NODE),"status","okay"))abort();expect("enabled controller rejected",-ENODEV);
 reset();defaults(false);if(fdt_setprop_string(dt,ofnode_path(NODE "/pci@0,0"),"status","okay"))abort();expect("enabled port rejected",-ENODEV);
 reset();defaults(false);if(fdt_setprop_string(dt,0,"compatible","apple,other"))abort();expect("wrong board rejected",-ENODEV);
 printf("PREFLIGHT-CASES %u PASS\n",cases);return 0;
}
'''
(r/'preflight-tests.c').write_text(pre+'\n#include "'+str(s/'lib/apple_pciec_m1.c')+'"\n#include "actual-preflight.inc"\n'+post)
subprocess.run(['gcc','-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer','-I'+str(h),str(r/'preflight-tests.c'),'-lfdt','-o',str(r/'preflight-tests')],check=True)
p=subprocess.run([str(r/'preflight-tests'),'/home/frank/usb4-test-work/uboot-hardware-test-20261031/probe47-pciec-generated-tunables/j274-probe-hv.dtb'],capture_output=True,text=True);(r/'preflight-tests.log').write_text(p.stdout+p.stderr);assert p.returncode==0,p.stderr
assert 'PREFLIGHT-CASES 32 PASS' in p.stdout
(r/'preflight-tests.json').write_text(json.dumps({'tests':32,'failures':0,'asan_ubsan_pass':True,'actual_production_preflight_body':True,'body_sha256':hashlib.sha256(body.encode()).hexdigest(),'dt_parser':'system libfdt with thin U-Boot API stubs','mmio_performed':False,'limitations':'No actual boot-stage generation emulation; supplies observed/proposed properties in test DT and checks rejection before mapping'},indent=2)+'\n');print(p.stdout[-250:])
