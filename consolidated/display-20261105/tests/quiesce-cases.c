static struct typec_altmode dpalt,tbtalt;
static int scenarios;
static struct cd321x fresh(void) {
 struct cd321x c={0}; c.port_altmode_dp=&dpalt; c.port_altmode_tbt=&tbtalt;
 c.state.mode=TYPEC_STATE_SAFE; c.mode_valid=true; c.tps.partner=(void *)1;
 fail_at=0;calls=0;role_fail=0;role=USB_ROLE_NONE; memset(logcalls,0,sizeof(logcalls)); return c;
}
static void clearcalls(void){calls=0; fail_at=0; role_fail=0; memset(logcalls,0,sizeof(logcalls));}
static void runwork(struct cd321x *c,u32 data) {
 c->update_status.status=TPS_STATUS_PLUG_PRESENT;
 c->update_status.data_status=data; c->tps.data_status=data;
 cd321x_update_work(&c->update_work.work);
}
static struct cd321x *callback_cd;
static int hpd_fail;
static bool inject_pending;
static int sink_hpd(void *data,bool high) {
 struct cd321x *cd=data;
 assert(cd==callback_cd && cd->dp_lock.held && !cd->tps.lock.held);
 call(high?'H':'L');
 if(inject_pending) {
  mutex_lock(&cd->tps.lock);
  cd->update_status.status=0;cd->update_status.data_status=0;
  mutex_unlock(&cd->tps.lock);inject_pending=false;
 }
 return hpd_fail?-EIO:0;
}
int main(void) {
 u32 data[]={0,TPS_DATA_STATUS_DATA_CONNECTION,
 TPS_DATA_STATUS_DATA_CONNECTION|TPS_DATA_STATUS_DP_CONNECTION|((TPS_DATA_STATUS_DP_SPEC_PIN_ASSIGNMENT_C>>1)<<10),
 TPS_DATA_STATUS_DATA_CONNECTION|TPS_DATA_STATUS_TBT_CONNECTION,
 TPS_DATA_STATUS_DATA_CONNECTION|CD321X_DATA_STATUS_USB4_CONNECTION};
 const char *order[]={"TM","TM","TM","MT","MT"};
 for(unsigned i=0;i<5;i++) {
  for(int failure=0;failure<=2;failure++) {
   struct cd321x c=fresh(); c.mode_valid=false;
   struct cd321x_status st={.data_status=data[i]};
   fail_at=failure;
   int r=cd321x_typec_update_mode(&c.tps,&st);
   assert(r==(failure?-EIO:0));
   assert(c.mode_valid==!failure);
   assert(c.state.data==NULL);
   if(failure) {
    assert(c.state.mode==TYPEC_STATE_SAFE && !c.state.alt);
    assert(calls==failure && !strncmp(logcalls,order[i],failure));
    clearcalls();
    assert(cd321x_typec_update_mode(&c.tps,&st)==0);
    assert(c.mode_valid && !strcmp(logcalls,order[i]));
   } else assert(!strcmp(logcalls,order[i]));
   clearcalls(); assert(cd321x_typec_update_mode(&c.tps,&st)==0); assert(calls==0);
   // Invalidating an unchanged cached mode must force both provider calls.
   c.mode_valid=false; assert(cd321x_typec_update_mode(&c.tps,&st)==0);
   assert(!strcmp(logcalls,order[i])); scenarios++;
  }
 }
 // DP assignments A-F and invalid encoding 5: never silently accept malformed data.
 for(unsigned pin=0;pin<8;pin++) {
  struct cd321x c=fresh(); struct cd321x_status st={.data_status=TPS_DATA_STATUS_DATA_CONNECTION|TPS_DATA_STATUS_DP_CONNECTION|((pin>>1)<<10)|((pin&1)?TPS_DATA_STATUS_USB3_CONNECTION:0)};
  int r=cd321x_typec_update_mode(&c.tps,&st);
  assert(r==((pin==5 || pin==7)?-EINVAL:0));
  if(r) assert(calls==0 && c.state.mode==TYPEC_STATE_SAFE);
  scenarios++;
 }
 // Worker must not enable the host after either provider fails, on every data route.
 for(unsigned i=1;i<5;i++) for(int failure=1;failure<=2;failure++) {
  struct cd321x c=fresh(); fail_at=failure;
  runwork(&c,data[i]|TPS_DATA_STATUS_USB3_CONNECTION);
  assert(role==USB_ROLE_NONE && !strchr(logcalls,'R') && !c.mode_valid);
  clearcalls(); runwork(&c,data[i]|TPS_DATA_STATUS_USB3_CONNECTION);
  assert(role==USB_ROLE_HOST && c.mode_valid && logcalls[calls-1]=='R'); scenarios++;
 }
 // Existing USB4->USB and USB->USB4 same-host-role quiescence must survive.
 for(int direction=0;direction<2;direction++) {
  struct cd321x c=fresh(); role=USB_ROLE_HOST;
  c.state.mode=direction?TYPEC_STATE_USB:TYPEC_MODE_USB4;
  runwork(&c,data[direction?4:1]|TPS_DATA_STATUS_USB3_CONNECTION);
  assert(logcalls[0]=='Q' && logcalls[calls-1]=='R' && role==USB_ROLE_HOST); scenarios++;
 }
 // Quiesce failure prevents every mux write.
 {struct cd321x c=fresh(); role=USB_ROLE_HOST; c.state.mode=TYPEC_MODE_USB4; fail_at=1;
 runwork(&c,data[1]|TPS_DATA_STATUS_USB3_CONNECTION); assert(!strcmp(logcalls,"Q")); scenarios++;}
 // Role activation failure invalidates cache, forcing a full provider replay.
 {struct cd321x c=fresh(); role_fail=1; runwork(&c,data[4]|TPS_DATA_STATUS_USB3_CONNECTION);
 assert(!c.mode_valid && role==USB_ROLE_NONE); clearcalls();runwork(&c,data[4]|TPS_DATA_STATUS_USB3_CONNECTION);
 assert(!strcmp(logcalls,"MTR") && c.mode_valid);scenarios++;}
 // Disconnect failure never invents a successful SAFE hardware state.
 {struct cd321x c=fresh();c.state.mode=TYPEC_MODE_USB4;fail_at=1;
 cd321x_update_work(&c.update_work.work);assert(!c.mode_valid && c.state.mode==TYPEC_MODE_USB4);scenarios++;}
 // Disconnect then reconnect of the same mode must not take a stale no-op branch.
 {struct cd321x c=fresh();c.state.mode=TYPEC_MODE_USB4;
 cd321x_update_work(&c.update_work.work);assert(!c.mode_valid);
 clearcalls(); runwork(&c,data[4]|TPS_DATA_STATUS_USB3_CONNECTION);assert(!strcmp(logcalls,"MTR"));scenarios++;}
 // Differential check against the original function for successful transitions.
 for(unsigned from=0;from<5;from++) for(unsigned to=0;to<5;to++) for(int flip=0;flip<2;flip++) {
  struct cd321x c=fresh(); struct cd321x_status first={.data_status=data[from]};
  assert(cd321x_typec_update_mode(&c.tps,&first)==0);
  struct cd321x old=c;
  struct cd321x_status target={.data_status=data[to],.status=flip?TPS_STATUS_PLUG_UPSIDE_DOWN:0};
  clearcalls(); original_typec_update_mode(&old.tps,&target);
  char previous[32]; strcpy(previous,logcalls);
  clearcalls(); assert(cd321x_typec_update_mode(&c.tps,&target)==0);
  assert(!strcmp(logcalls,previous) && c.state.alt==old.state.alt && c.state.mode==old.state.mode && !c.state.data);
  scenarios++;
 }
 // Demonstrate the prior defect: failure was ignored and an applied mode invented.
 {struct cd321x old=fresh(); struct cd321x_status st={.data_status=data[4]};fail_at=1;
 original_typec_update_mode(&old.tps,&st);assert(old.state.mode==TYPEC_MODE_USB4 && calls==2);
 struct cd321x c=fresh();fail_at=1;assert(cd321x_typec_update_mode(&c.tps,&st)==-EIO);
 assert(c.state.mode==TYPEC_STATE_SAFE && !c.mode_valid && calls==1);scenarios++;}
 // Real unregister must drain queued updates before releasing provider/port resources.
 for(int pending=0;pending<2;pending++) {
  struct cd321x c=fresh();queued=pending;
  cd321x_unregister_port(&c.tps);
  assert(!queued && !strcmp(logcalls,"CTMAAP") && !c.mux && !c.tbt_switch && !c.port_altmode_dp && !c.port_altmode_tbt);
  scenarios++;
 }
 const u32 dp_high=TPS_DATA_STATUS_DATA_CONNECTION|TPS_DATA_STATUS_DP_CONNECTION|
                   (1<<10)|CD321X_DATA_STATUS_HPD_LEVEL;
 // Producer first: readiness attaches later and replays once outside the PD lock.
 {struct cd321x c=fresh();callback_cd=&c;hpd_fail=0;
 struct device dev={.data=&c.tps,.compatible=true};struct apple_cd321x_dp_sink sink={sink_hpd,&c};
 runwork(&c,dp_high);assert(c.dp_hpd && !strchr(logcalls,'H'));clearcalls();
 assert(apple_cd321x_dp_attach(&dev,&sink)==0 && !strcmp(logcalls,"H"));
 assert(apple_cd321x_dp_attach(&dev,&sink)==-EBUSY);
 clearcalls();runwork(&c,dp_high);assert(!strchr(logcalls,'H'));
 clearcalls();assert(apple_cd321x_dp_detach(&dev,&sink)==0 && !strcmp(logcalls,"L"));
 assert(!c.dp_sink && c.dp_hpd);clearcalls();
 assert(apple_cd321x_dp_attach(&dev,&sink)==0 && !strcmp(logcalls,"H"));scenarios++;}
 // Consumer first: attaching to low level never invents a connected monitor.
 {struct cd321x c=fresh();callback_cd=&c;struct device dev={&c.tps,true};
 struct apple_cd321x_dp_sink sink={sink_hpd,&c};
 assert(apple_cd321x_dp_attach(&dev,&sink)==0 && calls==0);runwork(&c,dp_high);
 assert(c.dp_hpd && logcalls[calls-1]=='H');scenarios++;}
 // Firmware withdrawal failure vetoes every subsequent mux/role write.
 {struct cd321x c=fresh();callback_cd=&c;struct apple_cd321x_dp_sink sink={sink_hpd,&c};c.dp_sink=&sink;
 runwork(&c,dp_high);clearcalls();hpd_fail=1;runwork(&c,data[4]|TPS_DATA_STATUS_USB3_CONNECTION);
 assert(!strcmp(logcalls,"L") && c.dp_hpd && c.state.alt==&dpalt);
 assert(c.dp_fault);hpd_fail=0;clearcalls();runwork(&c,data[4]|TPS_DATA_STATUS_USB3_CONNECTION);
 assert(calls==0 && c.dp_hpd);scenarios++;}
 // A queued disconnect before readiness must cancel replay of an earlier high.
 {struct cd321x c=fresh();callback_cd=&c;struct device dev={&c.tps,true};
 struct apple_cd321x_dp_sink sink={sink_hpd,&c};runwork(&c,dp_high);
 c.update_status.status=0;c.update_status.data_status=0;clearcalls();
 assert(apple_cd321x_dp_attach(&dev,&sink)==0 && calls==0 && !c.dp_hpd);
 cd321x_update_work(&c.update_work.work);assert(!strchr(logcalls,'H'));scenarios++;}
 // Disconnect arriving inside the withdrawal callback cancels the old transition.
 {struct cd321x c=fresh();callback_cd=&c;struct apple_cd321x_dp_sink sink={sink_hpd,&c};c.dp_sink=&sink;
 runwork(&c,dp_high);clearcalls();inject_pending=true;
 runwork(&c,data[4]|TPS_DATA_STATUS_USB3_CONNECTION);
 assert(!strcmp(logcalls,"L") && !c.dp_hpd);scenarios++;}
 // Disconnect arriving during connect is consumed next, never lost to the old snapshot.
 {struct cd321x c=fresh();callback_cd=&c;struct apple_cd321x_dp_sink sink={sink_hpd,&c};c.dp_sink=&sink;
 inject_pending=true;runwork(&c,dp_high);assert(c.dp_hpd);clearcalls();
 cd321x_update_work(&c.update_work.work);assert(logcalls[0]=='L' && !c.dp_hpd);scenarios++;}
 // Failed high notification after readiness can be partial: freeze even while cached low.
 {struct cd321x c=fresh();callback_cd=&c;struct apple_cd321x_dp_sink sink={sink_hpd,&c};c.dp_sink=&sink;
 hpd_fail=1;runwork(&c,dp_high);assert(c.dp_fault && !c.dp_hpd);hpd_fail=0;clearcalls();
 runwork(&c,data[4]);assert(calls==0);scenarios++;}
 // Failed initial replay leaves no consumer pointer and forbids further route writes.
 {struct cd321x c=fresh();callback_cd=&c;struct device dev={&c.tps,true};
 struct apple_cd321x_dp_sink sink={sink_hpd,&c};runwork(&c,dp_high);hpd_fail=1;clearcalls();
 assert(apple_cd321x_dp_attach(&dev,&sink)==-EIO && !c.dp_sink && c.dp_fault);
 clearcalls();runwork(&c,data[4]);assert(calls==0);hpd_fail=0;scenarios++;}
 // Detach drains the callback even if withdrawal fails; stale callback cannot survive.
 {struct cd321x c=fresh();callback_cd=&c;struct device dev={&c.tps,true};
 struct apple_cd321x_dp_sink sink={sink_hpd,&c};c.dp_sink=&sink;runwork(&c,dp_high);hpd_fail=1;clearcalls();
 assert(apple_cd321x_dp_detach(&dev,&sink)==-EIO && !c.dp_sink && c.dp_fault);
 clearcalls();runwork(&c,data[1]);assert(calls==0);hpd_fail=0;scenarios++;}
 // Reject wrong providers/consumers and stopped instances without calling firmware.
 {struct cd321x c=fresh();callback_cd=&c;struct device dev={&c.tps,false};
 struct apple_cd321x_dp_sink sink={sink_hpd,&c},other={sink_hpd,&c};
 assert(apple_cd321x_dp_attach(&dev,&sink)==-ENODEV);dev.compatible=true;
 assert(apple_cd321x_dp_attach(&dev,NULL)==-EINVAL);
 assert(apple_cd321x_dp_attach(&dev,&sink)==0);
 assert(apple_cd321x_dp_detach(&dev,&other)==-ENOENT && c.dp_sink==&sink);
 assert(apple_cd321x_dp_detach(&dev,&sink)==0);c.dp_stopping=true;
 assert(apple_cd321x_dp_attach(&dev,&sink)==-ESHUTDOWN && calls==0);scenarios++;}
 // USB4/TB flags cannot be treated as native HPD even with DP/HPD bits set.
 {struct cd321x_status st={.status=TPS_STATUS_PLUG_PRESENT,.data_status=dp_high};
 assert(cd321x_native_dp_high(&st));st.data_status|=CD321X_DATA_STATUS_USB4_CONNECTION;
 assert(!cd321x_native_dp_high(&st));st.data_status=dp_high|TPS_DATA_STATUS_TBT_CONNECTION;
 assert(!cd321x_native_dp_high(&st));scenarios++;}

 // Late DP negotiation must quiesce an already-running USB host before changing pins.
 for(int direction=0;direction<2;direction++) for(int failure=0;failure<=1;failure++) {
  struct cd321x c=fresh();role=USB_ROLE_HOST;c.state.mode=TYPEC_STATE_USB;
  u32 dp=data[2]|TPS_DATA_STATUS_USB3_CONNECTION;
  if(direction){c.state.alt=&dpalt;c.state.mode=TYPEC_DP_STATE_D;c.dp_applied_data=dp;}
  fail_at=failure;runwork(&c,direction?(data[1]|TPS_DATA_STATUS_USB3_CONNECTION):dp);
  if(failure)assert(!strcmp(logcalls,"Q"));
  else assert(!strcmp(logcalls,"QTMR") && role==USB_ROLE_HOST);
  scenarios++;
 }
 // A DP pin change with the same role also stops the host; repeated HPD does not.
 {struct cd321x c=fresh();role=USB_ROLE_HOST;c.state.alt=&dpalt;c.state.mode=TYPEC_DP_STATE_D;
  c.dp_applied_data=data[2]|TPS_DATA_STATUS_USB3_CONNECTION;
  u32 target=TPS_DATA_STATUS_DATA_CONNECTION|TPS_DATA_STATUS_DP_CONNECTION|TPS_DATA_STATUS_USB2_CONNECTION|(2<<10);
  runwork(&c,target);assert(!strcmp(logcalls,"QTMR"));clearcalls();
  runwork(&c,target);assert(!strcmp(logcalls,"R"));scenarios+=2;}
 // Unchanged USB3 and USB4 routes must not unnecessarily reset their storage host.
 for(int usb4=0;usb4<2;usb4++) {
  struct cd321x c=fresh();role=USB_ROLE_HOST;c.state.mode=usb4?TYPEC_MODE_USB4:TYPEC_STATE_USB;
  runwork(&c,data[usb4?4:1]|TPS_DATA_STATUS_USB3_CONNECTION);
  assert(!strcmp(logcalls,"R"));scenarios++;
 }
 printf("PASS: %d fault/transition scenarios; actual driver functions; ASan/UBSan\n",scenarios);
 return 0;
}
