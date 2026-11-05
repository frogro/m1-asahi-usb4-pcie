#!/usr/bin/env python3
from pathlib import Path
import subprocess,json
w=Path(__file__).resolve().parent
import sys
src=Path(sys.argv[1])/'drivers/gpu/drm/apple/auto-dp.inc'
s=src.read_text();s=s[s.index('static int dcp_auto_dp_drain('):s.index('static int dcp_auto_dp_start(')]
pre=r'''
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <assert.h>
#include <string.h>
#include "dcp-route-policy.h"
typedef unsigned char u8;
struct device {struct device *parent;};
struct mutex {int held;};
struct work_struct {int scheduled;};
struct notifier_block {int dummy;};
struct epic_ep {void *wq;};
struct apple_epic_service {struct epic_ep *ep;int lock;unsigned long cmd_map[1];};
union phy_configure_opts {int dummy;};
struct dptx_port {struct apple_epic_service *service;bool connected;u64 dpin_token;union phy_configure_opts phy_ops;int lane_count,link_rate,pending_link_rate,route_type;void *dpin_provider,*atcphy;bool dpin_attempted,dpin_withdraw_attempted,dpin_withdrawn,dpin_reconnect_attempted;};
struct apple_dcp;
struct dcp_auto_route {struct apple_dcp *dcp;void *provider,*phy,*mux;u64 generation,event_sequence,output_route;unsigned int id,phy_index;u8 output_port;bool native,mux_owned;};
struct apple_dcp {struct dptx_port dptxport[1];struct mutex dp91_mutex;struct dcp_auto_route auto_dp_routes[4];struct apple_dp_policy auto_dp_policy;struct work_struct auto_dp_work;struct notifier_block auto_dp_notifier;bool auto_dp_ready;void *phy,*dev;int dptx_phy,index;};
struct codex_dp110_event {struct device *controller;u64 sequence,output_route;u8 output_port,input_index;};
#define DPTX_ROUTE_PHY 0
#define DPTX_ROUTE_USB4 1
#define CODEX_DP_BEFORE_RETIREMENT 0
#define CODEX_DP_PATHS_READY 1
#define CODEX_DP_CONTROLLER_RETIRING 2
#define CODEX_DPIN_END 4
#define NOTIFY_DONE 0
#define notifier_from_errno(x) (x)
#define READ_ONCE(x) (x)
#define WRITE_ONCE(x,v) ((x)=(v))
#define MAX_PENDING_CMDS 1
#define dev_info(...) ((void)0)
#define container_of(p,t,m) ((t *)((char *)(p)-offsetof(t,m)))
#define lockdep_assert_held(m) assert((m)->held)
#define spin_lock_irqsave(l,f) do{assert(!*(l));*(l)=1;(f)=0;}while(0)
#define spin_unlock_irqrestore(l,f) do{assert(*(l));*(l)=0;(void)(f);}while(0)
static void mutex_lock(struct mutex *m){assert(!m->held);m->held=1;}
static void mutex_unlock(struct mutex *m){assert(m->held);m->held=0;}
static void schedule_work(struct work_struct *w){w->scheduled++;}
static bool bitmap_empty(unsigned long *b,int size){assert(size==1);return !*b;}
static char events[128];static int ncalls,fail;static struct apple_dcp *active;
static int event(char e){assert(ncalls<127);events[ncalls++]=e;events[ncalls]=0;return ncalls==fail?-EIO:0;}
static void flush_workqueue(void *w){(void)w;event('F');}
static int mux_control_try_select(void *m,int index){assert(m&&index==0);return event('M');}
static int mux_control_deselect(void *m){assert(m);return event('m');}
static int dcp_native_dp_hpd(struct apple_dcp *d,bool up){int r=event(up?'N':'n');assert(!d->dptxport[0].dpin_provider);if(!r)d->dptxport[0].connected=up;return r;}
static int dp118_connect_locked(struct apple_dcp *d,bool reconnect){assert(!reconnect);assert(d->dptxport[0].dpin_provider);int r=event('D');if(!r){d->dptxport[0].connected=true;d->dptxport[0].dpin_token=99;}return r;}
static int dp107_withdraw(struct apple_dcp *d){assert(d->dptxport[0].dpin_token==99);int r=event('d');if(!r)d->dptxport[0].connected=false;return r;}
static int codex_dpin_call(void *p,u64 token,int op,int rate){assert(p&&token==99&&op==CODEX_DPIN_END&&!rate);return event('E');}
static struct epic_ep ep;static struct apple_epic_service service;
static struct device provider[4];
static void init(struct apple_dcp *d){memset(d,0,sizeof(*d));memset(&service,0,sizeof(service));service.ep=&ep;d->dptxport[0].service=&service;apple_dp_policy_init(&d->auto_dp_policy);d->auto_dp_ready=true;for(int i=0;i<4;i++){d->auto_dp_routes[i]=(struct dcp_auto_route){.dcp=d,.id=i,.phy_index=i%2,.native=i>=2,.provider=&provider[i],.phy=(void *)1,.mux=(void *)2};}active=d;ncalls=fail=0;events[0]=0;}
'''
cases=r'''
int main(void){struct apple_dcp d;int count=0;
 /* A native sink waits while dock is active; physical unplug retires the dock. */
 init(&d);struct device ctrl={.parent=&provider[1]};struct codex_dp110_event e={.controller=&ctrl,.sequence=1,.output_route=44,.output_port=6};
 assert(!dcp_auto_dp_notify(&d.auto_dp_notifier,CODEX_DP_PATHS_READY,&e));
 dcp_auto_dp_work(&d.auto_dp_work);assert(d.auto_dp_policy.owner==1&&!strcmp(events,"D"));
 assert(!dcp_auto_dp_native_hpd(&d.auto_dp_routes[2],true));dcp_auto_dp_work(&d.auto_dp_work);assert(!strcmp(events,"D"));
 e.sequence++;assert(!dcp_auto_dp_notify(&d.auto_dp_notifier,CODEX_DP_BEFORE_RETIREMENT,&e));
 assert(d.auto_dp_policy.owner==-1&&!strcmp(events,"DdFE"));
 dcp_auto_dp_work(&d.auto_dp_work);assert(d.auto_dp_policy.owner==2&&!strcmp(events,"DdFEMN"));
 assert(!dcp_auto_dp_native_hpd(&d.auto_dp_routes[2],false));assert(!strcmp(events,"DdFEMNnFm"));count++;
 /* Native port1 first; dock port0 arrives later and must wait. */
 init(&d);assert(!dcp_auto_dp_native_hpd(&d.auto_dp_routes[3],true));dcp_auto_dp_work(&d.auto_dp_work);assert(d.dptx_phy==1);
 ctrl.parent=&provider[0];e.sequence=1;assert(!dcp_auto_dp_notify(&d.auto_dp_notifier,CODEX_DP_PATHS_READY,&e));dcp_auto_dp_work(&d.auto_dp_work);assert(d.auto_dp_policy.owner==3);
 assert(!dcp_auto_dp_native_hpd(&d.auto_dp_routes[3],false));dcp_auto_dp_work(&d.auto_dp_work);assert(d.auto_dp_policy.owner==0&&d.dptx_phy==0);count++;
 /* Duplicate ready must not reconnect. Foreign/stale events cannot retire us. */
 int old=ncalls;e.sequence++;assert(!dcp_auto_dp_notify(&d.auto_dp_notifier,CODEX_DP_PATHS_READY,&e));dcp_auto_dp_work(&d.auto_dp_work);assert(ncalls==old);
 assert(dcp_auto_dp_notify(&d.auto_dp_notifier,CODEX_DP_BEFORE_RETIREMENT,&e)==-ESTALE);assert(ncalls==old);count++;
 e.sequence++;e.output_route++;assert(dcp_auto_dp_notify(&d.auto_dp_notifier,CODEX_DP_PATHS_READY,&e)==-EUCLEAN);assert(d.auto_dp_policy.phase==APPLE_DP_FAULT);count++;
 /* Failure in either acquire path prevents a competing acquisition. */
 for(int route=0;route<4;route++){init(&d);fail=1;mutex_lock(&d.dp91_mutex);assert(!dcp_auto_dp_request(&d.auto_dp_routes[route],true));mutex_unlock(&d.dp91_mutex);dcp_auto_dp_work(&d.auto_dp_work);assert(d.auto_dp_policy.phase==APPLE_DP_FAULT);assert(dcp_auto_dp_native_hpd(&d.auto_dp_routes[2],true)==-EUCLEAN);assert(ncalls==1);count++;}
 /* Withdrawal, drain and release failures never admit the pending route. */
 for(int native=0;native<2;native++)for(int stage=0;stage<3;stage++){
  init(&d);int route=native?2:0;mutex_lock(&d.dp91_mutex);assert(!dcp_auto_dp_request(&d.auto_dp_routes[route],true));mutex_unlock(&d.dp91_mutex);dcp_auto_dp_work(&d.auto_dp_work);
  if(stage==0)fail=ncalls+1;else if(stage==1)service.cmd_map[0]=1;else fail=ncalls+3;
  mutex_lock(&d.dp91_mutex);assert(!dcp_auto_dp_request(&d.auto_dp_routes[3],true));assert(dcp_auto_dp_request(&d.auto_dp_routes[route],false)<0);mutex_unlock(&d.dp91_mutex);
  assert(d.auto_dp_policy.phase==APPLE_DP_FAULT&&d.auto_dp_policy.owner==route);old=ncalls;dcp_auto_dp_work(&d.auto_dp_work);assert(ncalls==old);mutex_lock(&d.dp91_mutex);assert(!dcp_auto_dp_request(&d.auto_dp_routes[1],false));mutex_unlock(&d.dp91_mutex);assert(ncalls==old);count++;
 }
 /* Pending unplug before worker starts does not touch firmware. */
 init(&d);assert(!dcp_auto_dp_native_hpd(&d.auto_dp_routes[2],true));assert(!dcp_auto_dp_native_hpd(&d.auto_dp_routes[2],false));dcp_auto_dp_work(&d.auto_dp_work);assert(ncalls==0);count++;
 printf("PASS: %d extracted integration scenarios; firmware/provider calls mocked\n",count);return 0;}
'''
p=w/'integration-test.c';p.write_text(pre+s+cases)
subprocess.run(['gcc','-std=gnu11','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-I'+str(w/'test-include'),str(p),'-o',str(w/'integration-test')],check=True)
r=subprocess.run([str(w/'integration-test')],capture_output=True,text=True);print(r.stdout+r.stderr,end='');r.check_returncode()
(w/'integration-test-result.json').write_text(json.dumps({'result':r.stdout.strip(),'extracted_source':str(src),'real_hardware':False,'real_concurrency':False,'sanitizers':['address','undefined']},indent=2)+'\n')
