#!/usr/bin/env python3
from pathlib import Path
import subprocess,json,sys
w=Path(__file__).resolve().parent
src=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else w.parent/'ubuntu-source'
s=(src/'drivers/gpu/drm/apple/native-dp.inc').read_text()
a=s.index('static int dcp_native_dp_hpd(');b=s.index('\nint dcp_native_dp_start(',a)
pre=r'''
#include <stdbool.h>
#include <stdio.h>
#include <assert.h>
#include <errno.h>
#include <string.h>
struct mutex {int held;};
static void mutex_lock(struct mutex *m){assert(!m->held);m->held=1;}
static void mutex_unlock(struct mutex *m){assert(m->held);m->held=0;}
struct dptx_port {bool enabled,connected; void *service,*dpin_provider,*atcphy; int linkcfg_completion;};
struct apple_dcp {bool native_dp_ready,native_dp_fault,crashed,active;void *phy,*avep,*connector,*dev;int dptx_phy,dptx_die;struct mutex hpd_mutex;struct dptx_port dptxport[1];};
#define dev_info(...) ((void)0)
#define dev_dbg(...) ((void)0)
#define dev_err(...) ((void)0)
#define DPTX_CONNECT_TIMEOUT 2000
static int fail,callcount;static char events[64];static struct apple_dcp *current;
static int event(char x){assert(callcount<63);events[callcount++]=x;events[callcount]=0;return callcount==fail?-EIO:0;}
static void reinit_completion(int *p){*p=0;}
static int wait_for_completion_timeout(int *p,int timeout){(void)p;assert(timeout==2000 && !current->hpd_mutex.held);return 0;}
static int dptxport_connect(void *s,int core,int phy,int die){(void)s;assert(core==0&&phy==current->dptx_phy&&die==current->dptx_die&&current->hpd_mutex.held);return event('C');}
static int dptxport_request_display(void *s){(void)s;assert(current->hpd_mutex.held);return event('R');}
static int dptxport_set_hpd(void *s,bool h){(void)s;assert(!current->hpd_mutex.held);return event(h?'H':'L');}
static int dptxport_set_hpd_timeout(void *s,bool h,unsigned int ms){assert(!h&&ms==5000);return dptxport_set_hpd(s,h);}
static int dptxport_release_display(void *s){(void)s;assert(current->hpd_mutex.held);return event('D');}
static void disconnected_hpd_event(void *s){(void)s;assert(!current->hpd_mutex.held);event('N');}
static void av_service_connect(void *s){(void)s;assert(!current->hpd_mutex.held);event('A');}
static void av_service_disconnect(void *s){(void)s;assert(!current->hpd_mutex.held);event('B');}
static struct apple_dcp fresh(void){callcount=fail=0;events[0]=0;struct apple_dcp d={.native_dp_ready=true,.active=true,.phy=(void *)1,.avep=(void *)1,.dptx_phy=1,.dptx_die=0,.dptxport={{.enabled=true,.service=(void *)1}}};return d;}
'''
cases=r'''
int main(void){int cases=0;
 for(int f=0;f<=3;f++) {struct apple_dcp d=fresh();current=&d;fail=f;
 int ret=dcp_native_dp_hpd(&d,true);assert(!d.hpd_mutex.held);
 if(f){assert(ret==-EIO && d.native_dp_fault && !d.dptxport[0].connected && callcount==f);
 assert(dcp_native_dp_hpd(&d,true)==-ENODEV && callcount==f);}
 else{assert(!ret && d.dptxport[0].connected && !strcmp(events,"CRHA"));
 assert(dcp_native_dp_hpd(&d,true)==0 && !strcmp(events,"CRHA"));}
 cases++;}
 for(int f=0;f<=2;f++){struct apple_dcp d=fresh();current=&d;d.dptxport[0].connected=true;fail=f;
 int ret=dcp_native_dp_hpd(&d,false);assert(!d.hpd_mutex.held);
 if(f){assert(ret==-EIO && d.native_dp_fault && d.dptxport[0].connected && callcount==f);}
 else{assert(!ret && !d.dptxport[0].connected && !strcmp(events,"LDNB"));
 assert(dcp_native_dp_hpd(&d,false)==0 && !strcmp(events,"LDNB"));}
 cases++;}
 for(int gate=0;gate<8;gate++){struct apple_dcp d=fresh();current=&d;
 switch(gate){case 0:d.native_dp_ready=false;break;case 1:d.native_dp_fault=true;break;
 case 2:d.crashed=true;break;case 3:d.active=false;break;case 4:d.dptxport[0].enabled=false;break;
 case 5:d.dptxport[0].service=NULL;break;case 6:d.dptxport[0].dpin_provider=(void *)1;break;case 7:d.phy=NULL;break;}
 assert(dcp_native_dp_hpd(&d,true)==-ENODEV && callcount==0 && !d.hpd_mutex.held);cases++;}
 printf("PASS: %d DCP firmware-failure/readiness/ownership scenarios; ASan/UBSan\n",cases);return 0;}
'''
p=w/'withdraw-consumer-test.c';p.write_text(pre+s[a:b]+cases)
subprocess.run(['gcc','-std=gnu11','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',str(p),'-o',str(w/'withdraw-consumer-test')],check=True)
r=subprocess.run([str(w/'withdraw-consumer-test')],capture_output=True,text=True)
print(r.stdout+r.stderr,end='');r.check_returncode()
(w/'withdraw-consumer-result.json').write_text(json.dumps({'scope':'actual DCP native HPD handler, mocked firmware and locking, no hardware','result':r.stdout.strip()},indent=2)+'\n')
