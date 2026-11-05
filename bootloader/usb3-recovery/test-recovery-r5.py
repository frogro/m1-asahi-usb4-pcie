from pathlib import Path
import sys
import subprocess
p=Path(sys.argv[2]);p.mkdir(parents=True,exist_ok=True);s=Path(sys.argv[1]);t=(s/'drivers/usb/host/xhci.c').read_text();body=t[t.index('static int xhci_slot_command('):t.index('\n/*',t.index('static int _xhci_alloc_device('))]
pre=r'''
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <errno.h>
#include <stdbool.h>
typedef uint64_t dma_addr_t; typedef uint64_t u64;typedef uint32_t u32;
#define STS_HALT 1
#define STS_FATAL 4
#define STS_HCE 4096
#define MAX_HC_SLOTS 256
#define XHCI_TIMEOUT 5000
#define COMP_SUCCESS 1
#define COMP_TX_ERR 4
#define COMP_DEV_ERR 22
#define COMP_CTX_STATE 19
#define TRB_COMPLETION 33
#define TRB_ENABLE_SLOT 9
#define TRB_DISABLE_SLOT 10
#define TRB_ADDR_DEV 11
#define USB_SPEED_SUPER 5
#define SLOT_FLAG 1
#define EP0_FLAG 2
#define HCS_MAX_SLOTS(x) ((x)&255)
#define TRB_TO_SLOT_ID(x) ((x)>>24)
#define GET_COMP_CODE(x) ((x)>>24)
#define le32_to_cpu(x) (x)
#define cpu_to_le32(x) (x)
typedef int trb_type;
union xhci_trb {struct {u32 field[4];}generic;struct {u64 cmd;u32 status,flags;}event_cmd;};
struct ctx {void*bytes;unsigned size;dma_addr_t dma;};
struct xhci_input_control_ctx {u32 drop_flags,add_flags;};
struct xhci_virt_device {struct ctx *in_ctx;};
struct hc {u32 cr_hcsparams1;};struct hcor {u32 or_usbsts;};
struct xhci_ctrl {bool m1_diag,m1_dma_failed;unsigned rootdev;struct hc*hccr;struct hcor*hcor;struct xhci_virt_device*devs[256];};
struct usb_device {unsigned slot_id,status,speed;bool enumeration_reset_needed;};
static struct hc hc;static struct xhci_ctrl ctrl;static union xhci_trb ev;
struct action {int type,code,id,wrongptr,timeout,wrongslot;};
static struct action script[32];static unsigned nscript,at,acks,frees,allocs,delays,commands;static int allocfail,dmabad,owned[256];static struct action current;static unsigned cmdslot;static dma_addr_t ptr;
static struct xhci_ctrl*xhci_get_ctrl(struct usb_device*u){(void)u;return &ctrl;}
static u32 xhci_readl(u32*p){return *p;}
static dma_addr_t xhci_queue_command(struct xhci_ctrl*c,dma_addr_t d,u32 slot,u32 ep,trb_type type){(void)c;(void)d;(void)ep;assert(at<nscript);current=script[at++];assert(current.type==type);cmdslot=slot;commands++;ptr=0x1000+commands*16;return ptr;}
static union xhci_trb*xhci_wait_for_event_timeout(struct xhci_ctrl*c,int type,unsigned long timeout){(void)c;assert(timeout==5000);assert(type==TRB_COMPLETION);if(current.timeout)return NULL;unsigned id=current.type==TRB_ENABLE_SLOT?(unsigned)current.id:cmdslot;ev.event_cmd.cmd=ptr+(current.wrongptr?16:0);ev.event_cmd.status=current.code<<24;ev.event_cmd.flags=(id+(current.wrongslot?1:0))<<24;if(current.code==COMP_SUCCESS){if(current.type==TRB_ENABLE_SLOT&&id<256)owned[id]=1;if(current.type==TRB_DISABLE_SLOT)owned[id]=0;}return &ev;}
static void xhci_acknowledge_event(struct xhci_ctrl*c){(void)c;acks++;}
static int xhci_alloc_virt_device(struct xhci_ctrl*c,unsigned id){assert(id&&id<256&&!c->devs[id]);allocs++;if(allocfail)return -ENOMEM;c->devs[id]=calloc(1,sizeof(*c->devs[id]));c->devs[id]->in_ctx=calloc(1,sizeof(struct ctx));struct ctx*t=c->devs[id]->in_ctx;t->bytes=calloc(1,64);t->size=64;t->dma=0x8000+id*256;if(dmabad)c->m1_dma_failed=1;return 0;}
static void xhci_free_virt_device(struct xhci_ctrl*c,unsigned id){assert(!owned[id]);if(c->devs[id]){free(c->devs[id]->in_ctx->bytes);free(c->devs[id]->in_ctx);free(c->devs[id]);c->devs[id]=NULL;}frees++;}
static void xhci_setup_addressable_virt_dev(struct xhci_ctrl*c,struct usb_device*u,int port){(void)port;assert(c->devs[u->slot_id]);}
static struct xhci_input_control_ctx*xhci_get_input_control_ctx(struct ctx*c){return c->bytes;}
static void xhci_flush_cache(uintptr_t a,unsigned n){assert(a&&n);}
static void mdelay(unsigned ms){assert(ms==200);delays++;}
'''
post=r'''
static void reset(struct usb_device*u){for(unsigned i=1;i<256;i++)if(ctrl.devs[i]){owned[i]=0;xhci_free_virt_device(&ctrl,i);}memset(&ctrl,0,sizeof(ctrl));memset(owned,0,sizeof(owned));memset(script,0,sizeof(script));hc.cr_hcsparams1=32;ctrl.hccr=&hc;ctrl.rootdev=1;ctrl.m1_diag=1;at=nscript=acks=frees=allocs=delays=commands=0;allocfail=dmabad=0;u->enumeration_reset_needed=false;u->slot_id=1;u->status=123;u->speed=5;xhci_alloc_virt_device(&ctrl,1);owned[1]=1;allocs=0;}
static void add(int type,int code,int id){script[nscript++]=(struct action){.type=type,.code=code,.id=id};}
int main(void){struct usb_device u;unsigned cases=0;
#define CHECK(x) do{assert(x);cases++;}while(0)
reset(&u);add(TRB_ADDR_DEV,COMP_SUCCESS,0);CHECK(!xhci_address_device(&u,1));CHECK(u.status==0&&commands==1&&!frees&&!allocs&&!delays);
for(unsigned failures=1;failures<4;failures++){reset(&u);for(unsigned i=0;i<failures;i++){add(TRB_ADDR_DEV,COMP_TX_ERR,0);add(TRB_DISABLE_SLOT,COMP_SUCCESS,0);add(TRB_ENABLE_SLOT,COMP_SUCCESS,i+2);}add(TRB_ADDR_DEV,COMP_SUCCESS,0);CHECK(!xhci_address_device(&u,1));CHECK(frees==failures&&allocs==failures&&delays==failures&&u.slot_id==failures+1&&at==nscript);}
reset(&u);for(unsigned i=0;i<4;i++){add(TRB_ADDR_DEV,COMP_TX_ERR,0);add(TRB_DISABLE_SLOT,COMP_SUCCESS,0);if(i<3)add(TRB_ENABLE_SLOT,COMP_SUCCESS,i+2);}CHECK(xhci_address_device(&u,1)==-EPROTO);CHECK(u.enumeration_reset_needed);CHECK(frees==4&&allocs==3&&delays==3&&!u.slot_id&&at==nscript);
for(unsigned fault=0;fault<3;fault++){reset(&u);add(TRB_ADDR_DEV,COMP_TX_ERR,0);if(fault==0)script[0].timeout=1;if(fault==1)script[0].wrongptr=1;if(fault==2)script[0].wrongslot=1;CHECK(xhci_address_device(&u,1)<0);CHECK(!frees&&!allocs&&!delays&&commands==1);CHECK(acks==(fault?1:0));}
for(unsigned fault=0;fault<4;fault++){reset(&u);add(TRB_ADDR_DEV,COMP_TX_ERR,0);add(TRB_DISABLE_SLOT,COMP_SUCCESS,0);if(fault==0)script[1].timeout=1;if(fault==1)script[1].wrongptr=1;if(fault==2)script[1].wrongslot=1;if(fault==3)script[1].code=COMP_CTX_STATE;CHECK(xhci_address_device(&u,1)<0);CHECK(!frees&&!allocs&&!delays&&commands==2&&u.slot_id==1);}
for(unsigned fault=0;fault<6;fault++){reset(&u);add(TRB_ADDR_DEV,COMP_TX_ERR,0);add(TRB_DISABLE_SLOT,COMP_SUCCESS,0);add(TRB_ENABLE_SLOT,COMP_SUCCESS,2);if(fault==0)script[2].timeout=1;if(fault==1)script[2].wrongptr=1;if(fault==2)script[2].code=COMP_CTX_STATE;if(fault==3)script[2].id=0;if(fault==4)script[2].id=33;if(fault==5){script[2].id=10;xhci_alloc_virt_device(&ctrl,10);owned[10]=1;allocs=0;}CHECK(xhci_address_device(&u,1)<0);CHECK(frees==1&&!allocs&&commands==3);}
for(unsigned cc=0;cc<32;cc++){if(cc==COMP_SUCCESS||cc==COMP_TX_ERR)continue;reset(&u);add(TRB_ADDR_DEV,cc,0);CHECK(xhci_address_device(&u,1)<0);CHECK(!frees&&!allocs&&!delays&&commands==1);}
reset(&u);ctrl.m1_dma_failed=1;CHECK(xhci_address_device(&u,1)==-EFAULT);CHECK(!commands&&!frees);
reset(&u);ctrl.rootdev=0;CHECK(!_xhci_alloc_device(&u));CHECK(!commands);
reset(&u);u.slot_id=0;add(TRB_ENABLE_SLOT,COMP_SUCCESS,2);CHECK(!_xhci_alloc_device(&u));CHECK(u.slot_id==2&&allocs==1&&owned[1]);
reset(&u);u.slot_id=0;allocfail=1;add(TRB_ENABLE_SLOT,COMP_SUCCESS,2);add(TRB_DISABLE_SLOT,COMP_SUCCESS,0);CHECK(_xhci_alloc_device(&u)==-ENOMEM);CHECK(u.slot_id==0&&frees==1&&owned[1]);
reset(&u);u.slot_id=0;dmabad=1;add(TRB_ENABLE_SLOT,COMP_SUCCESS,2);CHECK(_xhci_alloc_device(&u)==-EFAULT);CHECK(!frees&&u.slot_id==2&&ctrl.devs[2]);
reset(&u);struct hcor stopped={.or_usbsts=0x15};ctrl.hcor=&stopped;CHECK(xhci_address_device(&u,1)==-EIO);CHECK(!commands&&!frees);
reset(&u);owned[1]=0;xhci_free_virt_device(&ctrl,1);printf("PASS %u recovery assertions using actual source functions\n",cases);return 0;}
'''
f=p/'recovery-harness.c';f.write_text(pre+body+post);subprocess.run(['cc','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-g',str(f),'-o',str(p/'recovery-harness')],check=True);r=subprocess.run([str(p/'recovery-harness')],text=True,capture_output=True);(p/'recovery-tests.log').write_text(r.stdout+r.stderr);r.check_returncode();print(r.stdout.splitlines()[-1])
