#!/usr/bin/env python3
"""Compile actual av.c lifecycle functions against a controlled RPC/ALSA harness."""
from pathlib import Path
import subprocess, sys, json, argparse
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('baseline',type=Path)
parser.add_argument('candidate',type=Path)
parser.add_argument('--output',required=True,type=Path)
args=parser.parse_args()
base=args.output.resolve();base.mkdir(parents=True,exist_ok=True)

def block(s, marker, struct=False):
 start=s.index(marker); brace=s.index('{',start); level=1; i=brace+1
 while level:
  level += (s[i]=='{')-(s[i]=='}'); i+=1
 return s[start:i]+(';' if struct else '')

preamble=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
typedef uint64_t u64;
typedef uint32_t u32;
typedef int64_t s64;
struct mutex { int held; };
struct rw_semaphore { int held; };
struct work_struct { int unused; };
struct platform_device { int unused; };
struct audiosrv_data;
struct apple_dcp { struct audiosrv_data *audiosrv; void *dev; };
struct apple_dcp_afkep { struct apple_dcp *dcp; };
struct apple_epic_service { struct apple_dcp_afkep *ep; unsigned channel; bool enabled, torndown; };
static void mutex_lock(struct mutex *m) { assert(!m->held); m->held=1; }
static void mutex_unlock(struct mutex *m) { assert(m->held); m->held=0; }
static void down_write(struct rw_semaphore *m) { assert(!m->held); m->held=1; }
static void up_write(struct rw_semaphore *m) { assert(m->held); m->held=0; }
#define scoped_guard(type,ptr) for(int once=1;once;once=0)
#define READ_ONCE(x) (x)
#define dev_info(...) ((void)0)
#define dev_err(...) ((void)0)
static int jack, opens, closes, rpc_error;
static void (*rpc_hook)(void);
static void schedule_work(struct work_struct *w) { (void)w; }
static void dcpaud_connect(struct platform_device *p, bool on) { (void)p; jack=on; }
static void dcpaud_disconnect(struct platform_device *p) { (void)p; jack=0; }
static int afk_service_call(struct apple_epic_service *, int, int, void *, int, int, void *, int, int);
'''
functions=['static void av_interface_init(', 'static void av_interface_teardown(', 'static void av_audiosrv_init(', 'static void av_audiosrv_teardown(', 'void av_service_connect(', 'void av_service_disconnect(']
body=r'''
static struct audiosrv_data state;
static struct apple_dcp dcp;
static struct apple_dcp_afkep ep;
static struct platform_device audio;
static struct apple_epic_service old_audio,new_audio,old_video,new_video;
static int afk_service_call(struct apple_epic_service *s,int group,int cmd,void *in,int ni,int pi,void *out,int no,int po) {
 (void)group;(void)in;(void)ni;(void)pi;(void)out;(void)no;(void)po;
 assert(s); assert(!state.plug_lock.held); assert(!state.srv_rwsem.held);
 if(cmd==1) opens++; else if(cmd==2) closes++; else abort();
 void (*fn)(void)=rpc_hook; rpc_hook=NULL; if(fn) fn();
 return rpc_error;
}
static void setup(void) {
 memset(&state,0,sizeof state); dcp.audiosrv=&state; ep.dcp=&dcp;
 state.audio_dev=&audio;state.cmds.open=1;state.cmds.close=2;
 old_audio=(struct apple_epic_service){&ep,1,true,false};
 new_audio=(struct apple_epic_service){&ep,2,true,false};
 old_video=(struct apple_epic_service){&ep,3,true,false};
 new_video=(struct apple_epic_service){&ep,4,true,false};
 jack=opens=closes=rpc_error=0;rpc_hook=NULL;
 av_interface_init(&old_video,NULL,NULL,0);av_audiosrv_init(&old_audio,NULL,NULL,0);
}
static void replace_audio(void) { av_audiosrv_init(&new_audio,NULL,NULL,0); }
static void unplug_video(void) { av_interface_teardown(&old_video); }
static void tear_audio(void) { old_audio.torndown=true; av_audiosrv_teardown(&old_audio); }
int main(int argc,char **argv) {
 assert(argc==2);setup();
 if(!strcmp(argv[1],"replacement_after_video_teardown")) {
  av_service_connect(&dcp); assert(jack && opens==1);
  unplug_video(); assert(!jack);
  av_interface_init(&new_video,NULL,NULL,0);replace_audio();av_service_connect(&dcp);
  assert(jack && opens==2);
 } else if(!strcmp(argv[1],"stale_audio_teardown")) {
  replace_audio();av_service_connect(&dcp);assert(jack);
  av_audiosrv_teardown(&old_audio);assert(jack && state.srv==&new_audio);
 } else if(!strcmp(argv[1],"replacement_during_open")) {
  rpc_hook=replace_audio;av_service_connect(&dcp);assert(!jack);
  av_service_connect(&dcp);assert(jack && opens==2);
 } else if(!strcmp(argv[1],"unplug_during_open")) {
  rpc_hook=unplug_video;av_service_connect(&dcp);assert(!jack);
  av_service_disconnect(&dcp);assert(closes==0);
 } else if(!strcmp(argv[1],"stale_video_teardown")) {
  av_interface_init(&new_video,NULL,NULL,0);replace_audio();av_service_connect(&dcp);
  av_interface_teardown(&old_video);assert(jack);
 } else if(!strcmp(argv[1],"close_callback_no_deadlock")) {
  av_service_connect(&dcp);rpc_hook=tear_audio;av_service_disconnect(&dcp);
  assert(!jack && closes==1);replace_audio();av_service_connect(&dcp);assert(jack);
 } else if(!strcmp(argv[1],"open_failure_retry")) {
  rpc_error=-5;av_service_connect(&dcp);assert(!jack);
  rpc_error=0;av_service_connect(&dcp);assert(jack && opens==2);
 } else if(!strcmp(argv[1],"idempotent_open")) {
  av_service_connect(&dcp);av_service_connect(&dcp);assert(jack && opens==1);
  av_service_disconnect(&dcp);av_service_disconnect(&dcp);assert(!jack && closes==1);
 } else abort();
 assert(!state.plug_lock.held && !state.srv_rwsem.held);
 puts("PASS");return 0;
}
'''
cases=['replacement_after_video_teardown','stale_audio_teardown','replacement_during_open','unplug_during_open','stale_video_teardown','close_callback_no_deadlock','open_failure_retry','idempotent_open']
results={}
for version in ['baseline','candidate']:
 s=getattr(args,version).read_text()
 code=preamble+'\n'+block(s,'struct dcp_av_audio_cmds {',True)+'\n'+block(s,'struct audiosrv_data {',True)+'\n'+'\n'.join(block(s,k) for k in functions)+'\n'+body
 out=base/f'test-{version}';out.with_suffix('.c').write_text(code)
 subprocess.run(['cc','-std=gnu11','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-g','-fsanitize=undefined','-o',str(out),str(out.with_suffix('.c'))],check=True)
 results[version]={}
 for case in cases:
  p=subprocess.run([str(out),case],capture_output=True,text=True,timeout=5)
  results[version][case]={'returncode':p.returncode,'stdout':p.stdout.strip(),'stderr':p.stderr.strip()}
print(json.dumps(results,indent=2));(base/'lifecycle-results.json').write_text(json.dumps(results,indent=2)+'\n')
assert results['baseline']['replacement_after_video_teardown']['returncode']!=0
assert all(x['returncode']==0 for x in results['candidate'].values())
