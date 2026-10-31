#include <stdint.h>
#include <stdio.h>
#include <assert.h>
#include <errno.h>
typedef uint32_t u32;
#define USB4_CFG_WRITE 2
static unsigned calls;
static int diagnostic_xfer(void*c,unsigned port,unsigned space,unsigned offset,unsigned words,u32 *data,unsigned type,uint64_t route){(void)c;assert(!port&&space==2&&words==1&&type==2&&!route);assert(offset==0x19||offset==0x1a);assert(data);calls++;return 0;}
static int diagnostic_query_write(void *context, unsigned int offset, u32 value)
{
 if ((offset == 0x19 && value != 0 && value != 5 && value != 6) ||
     (offset == 0x1a && value != 0x80000025 && value != 0x80000033 &&
      value != 0x80000010) || (offset != 0x19 && offset != 0x1a))
  return -EINVAL;
 return diagnostic_xfer(context, 0, 2, offset, 1, &value, USB4_CFG_WRITE, 0);
}

int main(void){unsigned cases=0;for(unsigned off=0;off<0x40;off++)for(unsigned v=0;v<256;v++){for(unsigned high=0;high<2;high++){u32 value=v|(high?0x80000000U:0);int ok=(off==0x19&&(value==0||value==5||value==6))||(off==0x1a&&(value==0x80000010U||value==0x80000025U||value==0x80000033U));calls=0;assert(diagnostic_query_write(0,off,value)==(ok?0:-EINVAL));assert(calls==(unsigned)ok);cases++;}}printf("WRITE ALLOWLIST: %u cases, zero failures\n",cases);}
