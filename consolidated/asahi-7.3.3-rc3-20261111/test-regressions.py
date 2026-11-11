#!/usr/bin/env python3
"""Compile real patched C functions with mocked I/O; no hardware access.
These tests cover return values, retries, state and cleanup, not bus timing.
"""
import argparse, json, resource, subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('kernel',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
def extract(path,name):
 return extract_text((a.kernel/path).read_text(), name)

def extract_text(s,name):
 import re
 m=re.search(r'^static [^\n]*\b'+name+r'\([^;]*?\n\{',s,re.M);assert m,name
 start=m.start();i=m.end();depth=1
 while depth:
  depth+=(s[i]=='{')-(s[i]=='}');i+=1
 return s[start:i]
common=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32; typedef uint64_t u64;
#define BIT(n) (1UL<<(n))
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
#define min_t(t,a,b) ((t)(a)<(t)(b)?(t)(a):(t)(b))
#define dev_err(...) ((void)0)
#define dev_warn(...) ((void)0)
#define dev_info(...) ((void)0)
#define dev_dbg(...) ((void)0)
'''
manifest=json.loads((Path(__file__).parent/'manifest.json').read_text())
results={}
baseline_functions={
 'amd-transfer': ('drivers/i2c/busses/i2c-designware-master.c','amd_i2c_dw_xfer_quirk'),
 'phy-state': ('drivers/phy/apple/atc.c','atcphy_configure_pipehandler'),
}
def test(name,prefix,body,suffix):
 code=common+prefix+'\n'+body+'\n'+suffix
 path=a.output/(name+'.c');path.write_text(code);exe=a.output/name
 subprocess.run(['cc','-std=gnu11','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-sign-compare','-O2',str(path),'-o',str(exe)],check=True)
 r=subprocess.run([str(exe)],check=True,capture_output=True,text=True);print(name,r.stdout.strip());results[name]=r.stdout.strip()
 if name in baseline_functions:
  source,function=baseline_functions[name]
  old=subprocess.check_output(['git','-C',str(a.kernel),'show',manifest['rc2_tree']+':'+source],text=True)
  old_code=common+prefix+'\n'+extract_text(old,function)+'\n'+suffix
  old_path=a.output/(name+'-before.c');old_path.write_text(old_code);old_exe=a.output/(name+'-before')
  subprocess.run(['cc','-std=gnu11','-O2',str(old_path),'-o',str(old_exe)],check=True)
  def no_core(): resource.setrlimit(resource.RLIMIT_CORE,(0,0))
  old_run=subprocess.run([str(old_exe)],capture_output=True,text=True,preexec_fn=no_core)
  if old_run.returncode != -6:
   raise SystemExit(f'{name}: expected an assertion failure on unpatched source, got {old_run.returncode}')
  results[name]+='; unpatched source fails the same assertions'
  print(name,'unpatched source fails as expected')

i2c='drivers/i2c/busses/i2c-designware-master.c'
test('amd-transfer',r'''
#define I2C_M_RD 1
#define PM_RUNTIME_ACQUIRE_AUTOSUSPEND(d,p) int p = pm_error
#define PM_RUNTIME_ACQUIRE_ERR(p) (*(p))
#define AMD_UCSI_INTR_REG 0
#define AMD_UCSI_INTR_EN 1
#define DW_IC_TX_TL 2
#define DW_IC_RX_TL 3
#define DW_IC_DATA_CMD 4
#define AMD_TIMEOUT_MIN_US 1
#define AMD_TIMEOUT_MAX_US 2
struct i2c_msg { unsigned flags,len; u8 *buf; };
struct dw_i2c_dev { void *dev,*map; struct i2c_msg *msgs; int msgs_num,msg_write_idx; };
static int pm_error,stop_error,status_error;
static void regmap_write(void *m,int r,int v) {}
static void regmap_read(void *m,int r,unsigned *v) {*v=42;}
static void i2c_dw_xfer_init(struct dw_i2c_dev *d) {}
static int i2c_dw_status(struct dw_i2c_dev *d) {return status_error;}
static int i2c_dw_check_stopbit(struct dw_i2c_dev *d) {return stop_error;}
static void usleep_range(int a,int b) {}
''',extract(i2c,'amd_i2c_dw_xfer_quirk'),r'''
int main(void) {
 struct dw_i2c_dev d={0}; u8 b[4]={0};struct i2c_msg m[2]={{.len=2,.buf=b},{.len=4,.buf=b,.flags=I2C_M_RD}};
 assert(amd_i2c_dw_xfer_quirk(&d,m,1)==1);
 assert(amd_i2c_dw_xfer_quirk(&d,m,2)==2);assert(b[0]==42);
 stop_error=-ETIMEDOUT;assert(amd_i2c_dw_xfer_quirk(&d,m,1)==-ETIMEDOUT);
 stop_error=0;status_error=-EIO;assert(amd_i2c_dw_xfer_quirk(&d,m,2)==-EIO);
 pm_error=-1;assert(amd_i2c_dw_xfer_quirk(&d,m,1)==-ENXIO);
 puts("5 transfer/PM/error cases passed");
}
''')
ccg='drivers/usb/typec/ucsi/ucsi_ccg.c'
test('ccg-transfer',r'''
#define I2C_M_RD 1
#define GFP_KERNEL 0
#define CCG_READ_MAX_RETRIES 4
struct i2c_adapter_quirks { unsigned max_read_len; };
struct i2c_adapter {const struct i2c_adapter_quirks *quirks;};
struct i2c_client {int addr;struct i2c_adapter *adapter;};
struct i2c_msg {int addr,flags,len;u8 *buf;};
struct ucsi_ccg {void *dev;struct i2c_client *client;};
static int pm,allocated,seq[10],calls,sleeps;
static void *kzalloc(size_t n,int f) {allocated++;return calloc(1,n);}
static void kfree(void *p) {allocated--;free(p);}
static void put_unaligned_le16(u16 n,u8 *p) {p[0]=n;p[1]=n>>8;}
static void pm_runtime_get_sync(void *d) {pm++;}
static void pm_runtime_put_sync(void *d) {pm--;}
static void fsleep(int n) {sleeps++;}
static int i2c_transfer(struct i2c_adapter *a,struct i2c_msg *m,int n) {return seq[calls++];}
static void reset(int x) {assert(pm==0&&allocated==0);calls=sleeps=0;for(int i=0;i<10;i++)seq[i]=x;}
''',extract(ccg,'ccg_read')+'\n'+extract(ccg,'ccg_write'),r'''
int main(void) {
 struct i2c_adapter_quirks q={.max_read_len=2};struct i2c_adapter a={.quirks=&q};
 struct i2c_client c={.addr=8,.adapter=&a};struct ucsi_ccg u={.client=&c};u8 b[4]={0};
 reset(2);assert(ccg_read(&u,0,b,4)==0&&calls==2);
 reset(1);assert(ccg_read(&u,0,b,4)==-EIO&&calls==1);
 reset(0);assert(ccg_read(&u,0,b,4)==-EIO);
 reset(-ETIMEDOUT);assert(ccg_read(&u,0,b,4)==-ETIMEDOUT&&calls==1&&sleeps==0);
 reset(-EREMOTEIO);assert(ccg_read(&u,0,b,4)==-EREMOTEIO&&calls==4&&sleeps==3);
 reset(2);seq[0]=-EREMOTEIO;assert(ccg_read(&u,0,b,4)==0&&calls==3&&sleeps==1);
 reset(1);assert(ccg_write(&u,0,b,4)==0);
 reset(0);assert(ccg_write(&u,0,b,4)==-EIO&&calls==1);
 reset(-EREMOTEIO);assert(ccg_write(&u,0,b,4)==-EREMOTEIO&&calls==1);
 reset(2);seq[1]=1;assert(ccg_read(&u,0,b,4)==-EIO&&calls==2);
 reset(0);puts("10 chunk/short-transfer/retry/PM/allocation cases passed");
}
''')
ucsi='drivers/usb/typec/ucsi/ucsi.c'
test('ucsi-retry',r'''
#define EPROBE_DEFER 517
#define HZ 1000
#define UCSI_RETRY_INIT_TIMEOUT BIT(3)
#define UCSI_ROLE_SWITCH_INTERVAL 100
#define UCSI_ROLE_SWITCH_WAIT_COUNT 100
#define system_dfl_long_wq 0
#define ERR_PTR(x) ((void *)(long)(x))
#define container_of(p,t,m) ((t *)((char *)(p)-offsetof(t,m)))
struct work_struct {int dummy;};struct delayed_work {struct work_struct work;};
struct ucsi {void *dev,*connector;struct delayed_work work;int work_count;bool init_timeout_retried;unsigned long quirks;};
static int init_result,queued,delay,errors;
static int ucsi_init(struct ucsi *u) {return init_result;}
static void queue_delayed_work(int q,struct delayed_work *w,int d) {queued++;delay=d;}
#define dev_err_probe(...) (++errors)
static void run(struct ucsi *u,int r);
''',extract(ucsi,'ucsi_init_work'),r'''
static void run(struct ucsi *u,int r) {queued=errors=delay=0;init_result=r;ucsi_init_work(&u->work.work);}
int main(void) {
 struct ucsi u={0};run(&u,-ETIMEDOUT);assert(!queued&&errors);
 u.quirks=UCSI_RETRY_INIT_TIMEOUT;run(&u,-ETIMEDOUT);assert(queued==1&&delay==HZ&&u.init_timeout_retried);
 run(&u,-ETIMEDOUT);assert(!queued&&errors);run(&u,0);assert(!queued&&!errors);
 for(int i=0;i<3;i++) {int r[]={-EINVAL,-ENODEV,-EPROBE_DEFER};u=(struct ucsi){0};run(&u,r[i]);assert(queued==1&&delay==100);}
 u=(struct ucsi){.quirks=UCSI_RETRY_INIT_TIMEOUT,.connector=&u};
 run(&u,-ETIMEDOUT);assert(!queued&&errors);run(&u,-EINVAL);assert(!queued&&errors);
 u=(struct ucsi){.work_count=100};run(&u,-ENODEV);assert(!queued);
 u=(struct ucsi){.quirks=UCSI_RETRY_INIT_TIMEOUT};run(&u,-EIO);assert(!queued&&errors);
 puts("11 init retry, limit, success and published-port cases passed");
}
''')
debug='drivers/usb/typec/ucsi/debugfs.c'
test('debugfs-null',r'''
struct connector {unsigned peak_current,avg_current,vbus_voltage;};struct ucsi {struct connector *connector;};struct seq_file {void *private;};
static unsigned printed;
#define seq_printf(m,f,v) (printed=(v))
''','\n'.join(extract(debug,n) for n in ['ucsi_peak_curr_show','ucsi_avg_curr_show','ucsi_vbus_volt_show']),r'''
int main(void) {struct ucsi u={0};struct seq_file m={&u};
 assert(ucsi_peak_curr_show(&m,0)==-ENODEV);assert(ucsi_avg_curr_show(&m,0)==-ENODEV);assert(ucsi_vbus_volt_show(&m,0)==-ENODEV);
 struct connector c={1,2,3};u.connector=&c;
 assert(ucsi_peak_curr_show(&m,0)==0&&printed==1);assert(ucsi_avg_curr_show(&m,0)==0&&printed==2);assert(ucsi_vbus_volt_show(&m,0)==0&&printed==3);
 puts("6 absent/present connector cases passed");}
''')
phy='drivers/phy/apple/atc.c'
test('phy-state',r'''
#define ATCPHY_PIPEHANDLER_STATE_USB3 0
#define ATCPHY_PIPEHANDLER_STATE_USB4 1
#define ATCPHY_PIPEHANDLER_STATE_DUMMY 2
#define lockdep_assert_held(x) ((void)0)
struct apple_atcphy {int lock,mode;bool pipehandler_up;};
static const struct {int pipehandler_state;} atcphy_modes[]={{0},{1},{2}};
static int result;
static int atcphy_configure_pipehandler_usb3(struct apple_atcphy *a,bool h) {return result;}
static int atcphy_configure_pipehandler_usb4(struct apple_atcphy *a) {return result;}
static int atcphy_configure_pipehandler_dummy(struct apple_atcphy *a) {return result;}
''',extract(phy,'atcphy_configure_pipehandler'),r'''
int main(void) {for(int m=0;m<2;m++) {struct apple_atcphy a={.mode=m};result=-ETIMEDOUT;assert(atcphy_configure_pipehandler(&a,true)==-ETIMEDOUT&&!a.pipehandler_up);result=0;assert(atcphy_configure_pipehandler(&a,true)==0&&a.pipehandler_up);}
 struct apple_atcphy a={.mode=2,.pipehandler_up=true};assert(atcphy_configure_pipehandler(&a,false)==0&&!a.pipehandler_up);
 puts("5 PIPE success/failure state cases passed");}
''')
test('phy-usb4-unwind',r'''
#define PIPEHANDLER_OVERRIDE_VALUES 0
#define PIPEHANDLER_OVERRIDE 1
#define PIPEHANDLER_OVERRIDE_VAL_RXDETECT0 1
#define PIPEHANDLER_OVERRIDE_VAL_RXDETECT1 2
#define PIPEHANDLER_OVERRIDE_RXVALID 4
#define PIPEHANDLER_OVERRIDE_RXDETECT 8
#define PIPEHANDLER_MUX_CTRL_DATA_USB4 2
#define PIPEHANDLER_MUX_CTRL_CLK_USB4 3
struct apple_atcphy {void *dev;struct {unsigned long pipehandler;} regs;};
static int check_result,lock_result,mux_calls,unlock_calls;static unsigned registers[2];
static int atcphy_pipehandler_check(struct apple_atcphy *a) {return check_result;}
static int atcphy_pipehandler_lock(struct apple_atcphy *a) {return lock_result;}
static int atcphy_pipehandler_unlock(struct apple_atcphy *a) {unlock_calls++;return 0;}
static void atcphy_pipehandler_set_mux(struct apple_atcphy *a,int b,int c) {mux_calls++;}
static void set32(unsigned long a,unsigned b) {registers[a]|=b;}
static void clear32(unsigned long a,unsigned b) {registers[a]&=~b;}
''',extract(phy,'atcphy_configure_pipehandler_usb4'),r'''
int main(void) {struct apple_atcphy a={0};
 lock_result=-ETIMEDOUT;assert(atcphy_configure_pipehandler_usb4(&a)==-ETIMEDOUT);assert(!registers[1]&&!mux_calls&&!unlock_calls);
 lock_result=0;assert(atcphy_configure_pipehandler_usb4(&a)==0);assert(!registers[1]&&mux_calls==1&&unlock_calls==1);
 check_result=-EIO;assert(atcphy_configure_pipehandler_usb4(&a)==-EIO&&mux_calls==1);
 puts("3 USB4 lock failure cleanup/success/precheck cases passed");}
''')
test('phy-mode-order',r'''
enum phy_mode {PHY_MODE_USB_HOST,PHY_MODE_USB_DEVICE,PHY_MODE_OTHER};
#define APPLE_ATCPHY_MODE_OFF 0
#define APPLE_ATCPHY_MODE_USB3 1
struct apple_atcphy {int lock,mode;bool pipehandler_up;};struct phy {struct apple_atcphy *data;};
static int configured,pipe_calls,result;
static struct apple_atcphy *phy_get_drvdata(struct phy *p) {return p->data;}
#define guard(x) no_op_guard
static void no_op_guard(void *p) {}
static int atcphy_configure(struct apple_atcphy *a,int m) {configured++;if(!result)a->mode=m;return result;}
static int atcphy_configure_pipehandler(struct apple_atcphy *a,bool host) {assert(!host);pipe_calls++;a->pipehandler_up=true;return 0;}
''',extract(phy,'atcphy_usb3_set_mode'),r'''
int main(void) {struct apple_atcphy a={0};struct phy p={&a};
 assert(atcphy_usb3_set_mode(&p,PHY_MODE_OTHER,0)==-EINVAL&&!configured&&!pipe_calls);
 result=-EIO;assert(atcphy_usb3_set_mode(&p,PHY_MODE_USB_HOST,0)==-EIO&&configured==1&&!pipe_calls);
 result=0;assert(atcphy_usb3_set_mode(&p,PHY_MODE_USB_HOST,0)==0&&configured==2&&pipe_calls==1);
 assert(atcphy_usb3_set_mode(&p,PHY_MODE_USB_HOST,0)==0&&configured==2&&pipe_calls==1);
 assert(atcphy_usb3_set_mode(&p,PHY_MODE_OTHER,0)==-EINVAL);
 puts("5 invalid-mode/power-failure/early-setup/duplicate-call cases passed");}
''')

test('ccg-cam-bounds',r'''
#define UCSI_MAX_ALTMODES 30
struct mode {u8 linked_idx,active_idx;};
struct ucsi_ccg {void *dev;struct mode orig[UCSI_MAX_ALTMODES],updated[UCSI_MAX_ALTMODES];};
''',extract(ccg,'ucsi_ccg_update_get_current_cam_cmd'),r'''
int main(void) {int cases=0;struct ucsi_ccg u={0};
 for(int c=0;c<256;c++) {u8 data=c;memset(u.updated,99,sizeof(u.updated));if(c<30)u.orig[c].linked_idx=29;
  int ret=ucsi_ccg_update_get_current_cam_cmd(&u,&data);assert(ret==(c<30?0:-EPROTO));
  if(c<30)assert(data==29&&u.updated[29].active_idx==c);else assert(data==c&&u.updated[29].active_idx==99);cases++;}
 for(int c=0;c<256;c++) {u8 data=0;u.orig[0].linked_idx=c;memset(u.updated,99,sizeof(u.updated));
  int ret=ucsi_ccg_update_get_current_cam_cmd(&u,&data);assert(ret==(c<30?0:-EPROTO));
  if(c<30)assert(data==c&&u.updated[c].active_idx==0);else assert(data==0&&u.updated[0].active_idx==99);cases++;}
 printf("%d firmware/translated-index bounds cases passed\n",cases);}
''')

(a.output/'results.json').write_text(json.dumps({'kind':'actual C functions with mocked hardware, no timing validation','tests':results},indent=2)+'\n')
