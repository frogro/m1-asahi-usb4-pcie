#!/usr/bin/env python3
"""Compile the actual driver functions with fault-injected provider calls."""
from pathlib import Path
import re, subprocess, json, sys, os
here=Path(__file__).resolve().parent
src=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else here.parent/'ubuntu-source'
core=(src/'drivers/usb/typec/tipd/core.c').read_text()
header=(src/'drivers/usb/typec/tipd/tps6598x.h').read_text()
constants=[]
for path in ['drivers/usb/typec/tipd/tps6598x.h','include/linux/usb/typec.h','include/linux/usb/typec_dp.h','include/linux/usb/typec_tbt.h']:
    data=(src/path).read_text().replace('\\\n', '')
    constants.extend(re.findall(r'^#define[^\n]*(?:\\\n[^\n]*)*',data,re.M))
a=core.index('static int cd321x_typec_update_mode(')
b=core.index('\nstatic void cd321x_queue_status(',a)
actual=(src/'drivers/usb/typec/tipd/native-dp.inc').read_text()+'\n'+core[a:b]
ua=core.index('static void\ncd321x_unregister_port(')
ub=core.index('\nstatic int tps_request_firmware(',ua)
actual += '\n' + core[ua:ub]
baseline=subprocess.run(['git','-C',str(src),'show',os.environ.get('ASAHI_TEST_BASE','HEAD')+':drivers/usb/typec/tipd/core.c'],check=True,text=True,capture_output=True).stdout
ba=baseline.index('static void cd321x_typec_update_mode(')
bb=baseline.index('\nstatic void cd321x_update_work(',ba)
original=baseline[ba:bb].replace('cd321x_typec_update_mode(', 'original_typec_update_mode(',1)
# Preserve real struct layouts for the state records; model unrelated kernel objects.
status=header[header.index('struct cd321x_status {'):header.index('\nstruct sn201202x {')]
pre=r'''
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint32_t u32;
#define BIT(x) (1UL << (x))
#define BIT_ULL(x) (1ULL << (x))
#define GENMASK(h,l) (((~0UL) << (l)) & (~0UL >> (63-(h))))
#define __bf_shf(x) (__builtin_ffsll(x)-1)
#define FIELD_GET(mask, val) (((val)&(mask)) >> __bf_shf(mask))
#define le32_to_cpu(x) (x)
#define le16_to_cpu(x) (x)
#define container_of(p,t,m) ((t *)((char *)(p)-offsetof(t,m)))
#define to_delayed_work(p) container_of(p,struct delayed_work,work)
struct mutex { int held; };
static void mutex_lock(struct mutex *m) {assert(!m->held);m->held=1;}
static void mutex_unlock(struct mutex *m) {assert(m->held);m->held=0;}
static struct mutex *take_guard(struct mutex *m){mutex_lock(m);return m;}
static void drop_guard(struct mutex **m){mutex_unlock(*m);}
#define CAT_(x,y) x##y
#define CAT(x,y) CAT_(x,y)
#define guard(x) struct mutex * __attribute__((cleanup(drop_guard))) CAT(guard_,__COUNTER__) = take_guard
#define lockdep_assert_held(m) assert((m)->held)
#define EXPORT_SYMBOL_GPL(x)
#define dev_warn_ratelimited(...) ((void)0)
struct device { void *data; bool compatible; };
static void *dev_get_drvdata(struct device *d) {return d->data;}
static bool device_is_compatible(struct device *d,const char *s) {(void)s;return d->compatible;}
struct apple_cd321x_dp_sink {int (*set_hpd)(void *,bool);void *data;};
#define dev_err(...) ((void)0)
#define dev_warn(...) ((void)0)
#define dev_info(...) ((void)0)
#define IS_ERR(x) false
struct work_struct { int x; };
struct delayed_work { struct work_struct work; };
struct typec_altmode { int x; };
struct typec_mux { int x; };
struct typec_thunderbolt_switch { int x; };
struct typec_mux_state { struct typec_altmode *alt; unsigned long mode; void *data; };
struct typec_displayport_data { u32 status, conf; };
struct typec_thunderbolt_data { u32 cable_mode,device_mode,enter_vdo; };
struct enter_usb_data { u32 eudo; bool active_link_training; };
enum usb_role { USB_ROLE_NONE,USB_ROLE_HOST,USB_ROLE_DEVICE };
enum typec_pwr_opmode { TYPEC_PWR_MODE_USB,TYPEC_PWR_MODE_1_5A,TYPEC_PWR_MODE_3_0A,TYPEC_PWR_MODE_PD };
enum typec_orientation { TYPEC_ORIENTATION_NONE,TYPEC_ORIENTATION_NORMAL,TYPEC_ORIENTATION_REVERSE };
enum { TYPEC_STATE_SAFE,TYPEC_STATE_USB,TYPEC_STATE_MODAL=2,TYPEC_MODE_USB4=6 };
enum { TYPEC_DP_STATE_A=2,TYPEC_DP_STATE_B,TYPEC_DP_STATE_C,TYPEC_DP_STATE_D,TYPEC_DP_STATE_E,TYPEC_DP_STATE_F };
enum { TYPEC_TBT_MODE=2,TYPEC_ACCESSORY_NONE=0 };
enum { TYPEC_THUNDERBOLT_SWITCH_OFF,TYPEC_THUNDERBOLT_SWITCH_TBT,TYPEC_THUNDERBOLT_SWITCH_USB4 };
struct typec_thunderbolt_switch_data { int state; enum typec_orientation orientation; struct typec_thunderbolt_data tbt; struct enter_usb_data usb4; };
struct usb_pd_identity { u32 data[6]; };
struct typec_partner_desc { bool usb_pd; int accessory; struct usb_pd_identity *identity; };
struct tps6598x_dp_sid_status_reg { u32 status_rx,configure; };
struct tps6598x_intel_vid_status_reg { uint16_t device_mode,enter_vdo; };
struct tps6598x_usb4_status_reg { u32 eudo; };
struct tps6598x { void *dev,*partner,*role_sw,*port,*psy; struct mutex lock; u32 data_status; };

static int fail_at,calls,role_fail; static char logcalls[32]; static enum usb_role role;
static int call(char c) { assert(calls<31); logcalls[calls++]=c; logcalls[calls]=0; return calls==fail_at?-EIO:0; }
static int typec_mux_set(struct typec_mux *m, struct typec_mux_state *s) {
 (void)m;
 if(s->mode==TYPEC_MODE_USB4 && !s->alt) assert(s->data);
 return call('M');
}
static int typec_thunderbolt_switch_set(struct typec_thunderbolt_switch *t, struct typec_thunderbolt_switch_data *s) {(void)t;(void)s;return call('T');}
static enum usb_role usb_role_switch_get_role(void *s) {(void)s;return role;}
static int usb_role_switch_set_role(void *s,enum usb_role r) {
 (void)s; int e=call(r==USB_ROLE_NONE?'Q':'R'); if(e)return e; if(r!=USB_ROLE_NONE && role_fail)return -EIO; role=r; return 0;
}
static bool queued;
static void cancel_delayed_work_sync(struct delayed_work *w) {(void)w;call('C');queued=false;}
static void typec_thunderbolt_switch_put(struct typec_thunderbolt_switch *p) {assert(!queued);(void)p;call('T');}
static void typec_mux_put(struct typec_mux *p) {assert(!queued);(void)p;call('M');}
static void typec_unregister_altmode(struct typec_altmode *p) {assert(!queued);(void)p;call('A');}
static void typec_unregister_port(void *p) {assert(!queued);(void)p;call('P');}
static void typec_unregister_partner(void *p){(void)p;}
static void *typec_register_partner(void *p,struct typec_partner_desc *d){(void)p;(void)d;return (void *)1;}
#define typec_partner_set_identity(...) ((void)0)
#define typec_set_mode(...) ((void)0)
#define typec_set_pwr_opmode(...) ((void)0)
#define typec_set_pwr_role(...) ((void)0)
#define typec_set_vconn_role(...) ((void)0)
#define typec_set_orientation(p,o) ((void)(p),(void)(o))
#define typec_set_data_role(...) ((void)0)
#define power_supply_changed(...) ((void)0)
'''
# Only define constants actually referenced, with recursively required dependencies.
byname={re.match(r'#define\s+(\w+)',d)[1]:d for d in constants if re.match(r'#define\s+(\w+)',d)}
used=set(re.findall(r'\b[A-Z][A-Z0-9_]+\b',actual))
needed={}
while True:
    todo=(used & byname.keys())-needed.keys()
    if not todo: break
    for n in todo:
        needed[n]=byname[n]
        used.update(re.findall(r'\b[A-Z][A-Z0-9_]+\b',byname[n]))
# Enum names above are deliberately mocked; macro constants come verbatim from kernel headers.
body=(here/'quiesce-cases.c').read_text()
text=pre+'\n'+'\n'.join(needed.values())+'\n'+status+'\n'+actual+'\n'+original+'\n'+body
(here/'quiesce-extracted-test.c').write_text(text)
subprocess.run(['gcc','-std=gnu11','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-omit-frame-pointer',str(here/'quiesce-extracted-test.c'),'-o',str(here/'quiesce-extracted-test')],check=True)
r=subprocess.run([str(here/'quiesce-extracted-test')],text=True,capture_output=True)
if r.returncode:
    print(r.stderr)
    r.check_returncode()
print(r.stdout,end='')
(here/'quiesce-test-result.json').write_text(json.dumps({'scope':'actual CD321x transition, HPD attach/replay/withdraw/detach functions; mocked locks/providers, not hardware or a concurrency stress test','sanitizers':['address','undefined'],'result':r.stdout.strip()},indent=2)+'\n')
