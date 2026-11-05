from pathlib import Path
import sys
import subprocess
p=Path(sys.argv[2]);p.mkdir(parents=True,exist_ok=True);s=Path(str(Path(sys.argv[1])/'common/usb_hub.c')).read_text();f=s[s.index('static int usb_hub_ssp_speed('):s.index('static int usb_hub_negotiated_speed(')]
pre=r'''
#include <stdint.h>
#include <stdbool.h>
#include <errno.h>
#include <assert.h>
#include <stdio.h>
#include <string.h>
typedef uint8_t u8;typedef uint32_t u32;
#define USB_DT_BOS 15
#define USB_SPEED_SUPER 5
#define USB_SPEED_SUPER_PLUS 6
static unsigned get_unaligned_le16(const void*p){const u8*b=p;return b[0]|b[1]<<8;}
static u32 get_unaligned_le32(const void*p){const u8*b=p;return (u32)b[0]|(u32)b[1]<<8|(u32)b[2]<<16|(u32)b[3]<<24;}
static void w32(u8*p,u32 v){for(int i=0;i<4;i++)p[i]=v>>(8*i);}
'''
post=r'''
int main(void){unsigned cases=0;u8 b[512]={5,15,25,0,1,20,16,10,0,1,0,0,0,1,0,0,0};u8 orig[512];
#define C(x) do{assert(x);cases++;}while(0)
w32(b+17,0x000a4031);w32(b+21,0x000a40b1);memcpy(orig,b,sizeof(b));
C(usb_hub_ssp_speed(b,25,0x11)==USB_SPEED_SUPER_PLUS);
C(usb_hub_ssp_speed(b,25,0x22)==-EINVAL);
C(usb_hub_ssp_speed(b,25,0x21)==-EOPNOTSUPP);
C(usb_hub_ssp_speed(b,25,0x1111)==-EOPNOTSUPP);
w32(b+17,0x00050031);C(usb_hub_ssp_speed(b,25,0x11)==USB_SPEED_SUPER);
w32(b+17,0x000a4071);C(usb_hub_ssp_speed(b,25,0x11)==-EOPNOTSUPP);
w32(b+17,0x000a8031);C(usb_hub_ssp_speed(b,25,0x11)==-EOPNOTSUPP);
w32(b+17,0x00054031);C(usb_hub_ssp_speed(b,25,0x11)==-EOPNOTSUPP);
for(unsigned len=0;len<25;len++){memcpy(b,orig,512);b[2]=len;C(usb_hub_ssp_speed(b,len,0x11)<0);}
memcpy(b,orig,512);b[5]=0;C(usb_hub_ssp_speed(b,25,0x11)==-EINVAL);
memcpy(b,orig,512);b[5]=255;C(usb_hub_ssp_speed(b,25,0x11)==-EINVAL);
memcpy(b,orig,512);b[9]=31;C(usb_hub_ssp_speed(b,25,0x11)==-EINVAL);
memcpy(b,orig,512);b[4]=2;C(usb_hub_ssp_speed(b,25,0x11)==-EINVAL);
memcpy(b,orig,512);w32(b+21,0x000a4031);C(usb_hub_ssp_speed(b,25,0x11)==-EOPNOTSUPP);
memcpy(b,orig,512);memcpy(b+25,b+5,20);b[2]=45;b[4]=2;C(usb_hub_ssp_speed(b,45,0x11)==-EINVAL);
b[0]=5;b[1]=15;b[2]=5;b[3]=0;b[4]=0;C(usb_hub_ssp_speed(b,5,0x11)==USB_SPEED_SUPER);
/* Every byte in a descriptor is varied under ASan/UBSan. */
for(unsigned i=0;i<25;i++)for(unsigned v=0;v<256;v++){memcpy(b,orig,512);b[i]=v;(void)usb_hub_ssp_speed(b,25,0x11);cases++;}
printf("PASS %u SSP parser checks using actual source function\n",cases);return 0;}
'''
out=p/'speed-harness.c';out.write_text(pre+f+post);subprocess.run(['cc','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-g',str(out),'-o',str(p/'speed-harness')],check=True);subprocess.run([str(p/'speed-harness')],check=True)