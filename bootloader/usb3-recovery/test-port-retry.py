from pathlib import Path
import sys
import subprocess
p=Path(sys.argv[2]);p.mkdir(parents=True,exist_ok=True);s=Path(sys.argv[1]);t=(s/'common/usb.c').read_text();body=t[t.index('int usb_setup_device('):t.index('\n#if !CONFIG_IS_ENABLED(DM_USB)',t.index('int usb_setup_device('))]
pre=r'''
#include <stdbool.h>
#include <errno.h>
#include <stdio.h>
#include <assert.h>
struct usb_device {int devnum,slot_id,portnr,speed;bool enumeration_reset_needed;};
static int calls,resets,selects,reset_result,first_result,second_result;static bool release;
static int usb_prepare_device(struct usb_device*d,int addr,bool read,struct usb_device*p){(void)read;(void)p;assert(addr==7);assert(!d->devnum&&!d->enumeration_reset_needed);d->devnum=addr;d->enumeration_reset_needed=release;calls++;return calls==1?first_result:second_result;}
static int usb_hub_reset_child(struct usb_device*p,int port,int speed){assert(p&&port==2&&speed==6);resets++;return reset_result;}
static int usb_select_config(struct usb_device*d){(void)d;selects++;return 0;}
'''
post=r'''
int main(void){struct usb_device hub={0},d;unsigned checks=0;
#define C(x) do{assert(x);checks++;}while(0)
#define RESET() do{d=(struct usb_device){.devnum=7,.portnr=2,.speed=6};calls=resets=selects=reset_result=0;release=true;first_result=-EPROTO;second_result=0;}while(0)
RESET();C(!usb_setup_device(&d,false,&hub));C(calls==2&&resets==1&&selects==1);
RESET();first_result=0;C(!usb_setup_device(&d,false,&hub));C(calls==1&&!resets&&selects==1);
RESET();second_result=-EPROTO;C(usb_setup_device(&d,false,&hub)==-EPROTO);C(calls==2&&resets==1&&!selects);
RESET();reset_result=-ETIMEDOUT;C(usb_setup_device(&d,false,&hub)==-ETIMEDOUT);C(calls==1&&resets==1&&!selects);
RESET();release=false;C(usb_setup_device(&d,false,&hub)==-EPROTO);C(calls==1&&!resets&&!selects);
RESET();d.slot_id=7;C(usb_setup_device(&d,false,&hub)==-EPROTO);C(calls==1&&!resets&&!selects);
RESET();C(usb_setup_device(&d,false,NULL)==-EPROTO);C(calls==1&&!resets&&!selects);
for(int e=1;e<140;e++){if(e==EPROTO)continue;RESET();first_result=-e;C(usb_setup_device(&d,false,&hub)==-e);C(calls==1&&!resets&&!selects);}
printf("PASS %u port-retry assertions using actual USB core source\n",checks);return 0;}
'''
f=p/'port-retry-harness.c';f.write_text(pre+body+post);subprocess.run(['cc','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-g',str(f),'-o',str(p/'port-retry-harness')],check=True);subprocess.run([str(p/'port-retry-harness')],check=True)
