#include <stdint.h>
#include <stdio.h>
#include <stdbool.h>
#include <string.h>
#include <errno.h>
#include <assert.h>
typedef uint32_t u32;
typedef int (*apple_nhi_read_fn)(void *,unsigned,unsigned,unsigned,unsigned,u32*);
typedef int (*apple_nhi_tmu_write_fn)(void *,unsigned,u32);
int apple_nhi_m1_query(apple_nhi_read_fn read, apple_nhi_tmu_write_fn write,
                      void (*wait)(void *), void *context, u32 opcode, u32 metadata)
{
 u32 value, data[16];
 unsigned int i, poll;
 int ret;
 if (!read || !write || !wait ||
     !((opcode == 0x25 || opcode == 0x33) ? metadata == 0 :
       opcode == 0x10 && (metadata == 5 || metadata == 6)))
  return -EINVAL;
 ret = read(context, 0, 2, 0x1a, 1, &value);
 if (ret) return ret;
 if (value & (1U << 31)) return -EBUSY;
 ret = write(context, 0x19, metadata);
 if (ret) return ret;
 ret = write(context, 0x1a, (1U << 31) | opcode);
 if (ret) return ret;
 for (poll = 0; poll < 10; poll++) {
  ret = read(context, 0, 2, 0x1a, 1, &value);
  if (ret) return ret;
  if (!(value & (1U << 31))) break;
  if (poll != 9) wait(context);
 }
 if (value & (1U << 31)) return -ETIMEDOUT;
 printf("NHI-QUERY opcode=%#x input=%#x completion=%08x polls=%u\n",
        opcode, metadata, value, poll + 1);
 if (value & (1U << 30)) return -EOPNOTSUPP;
 if ((value & 0x3f000000U) == 0x02000000U && opcode == 0x25)
  return -EOPNOTSUPP;
 if (value & 0x3f000000U) return -EIO;
 ret = read(context, 0, 2, 0x19, 1, &metadata);
 if (ret) return ret;
 printf("NHI-QUERY result opcode=%#x metadata=%08x\n", opcode, metadata);
 if (opcode == 0x33) {
  if ((metadata & 255) > 16) return -EMSGSIZE;
  ret = read(context, 0, 2, 9, 16, data);
  if (ret) return ret;
  for (i = 0; i < (metadata & 255); i++)
   printf("NHI-QUERY buffer[%u]=%08x\n", i, data[i]);
 }
 return 0;
}

struct fake { unsigned calls,fail,writes,reads,waits,polls,busy; u32 op,input,result,complete; bool initial_busy; };
static int rd(void *c,unsigned p,unsigned sp,unsigned o,unsigned n,u32 *v) {
 struct fake *f=c;assert(p==0&&sp==2);assert((n==1&&(o==0x19||o==0x1a))||(o==9&&n==16));
 f->calls++;f->reads++;if(f->calls==f->fail)return -EFAULT;
 if(o==0x1a) {*v=f->writes?(f->polls++<f->busy?0x80000000:f->complete):(f->initial_busy?0x80000000:0);}
 else if(o==0x19)*v=f->result;else for(unsigned i=0;i<n;i++)v[i]=i<<16|i;
 return 0;
}
static int wr(void*c,unsigned o,u32 v) {
 struct fake*f=c;assert((o==0x19&&v==f->input)||(o==0x1a&&v==(0x80000000|f->op)));
 f->calls++;f->writes++;if(f->calls==f->fail)return -EFAULT;return 0;
}
static void wt(void*c) {((struct fake*)c)->waits++;}
static struct fake fresh(u32 op,u32 in){return(struct fake){.op=op,.input=in,.result=op==0x33?5:0x1000,.complete=op};}
int main(void){unsigned cases=0;u32 ops[]={0x25,0x33,0x10,0x10},ins[]={0,0,5,6};
 for(unsigned i=0;i<4;i++) {
  struct fake f=fresh(ops[i],ins[i]);assert(!apple_nhi_m1_query(rd,wr,wt,&f,f.op,f.input));
  unsigned calls=f.calls;assert(f.writes==2&&f.waits==0);cases++;
  for(unsigned k=1;k<=calls;k++) {f=fresh(ops[i],ins[i]);f.fail=k;assert(apple_nhi_m1_query(rd,wr,wt,&f,f.op,f.input)==-EFAULT);assert(f.calls==k);cases++;}
  for(unsigned b=0;b<=10;b++) {f=fresh(ops[i],ins[i]);f.busy=b;int ret=apple_nhi_m1_query(rd,wr,wt,&f,f.op,f.input);assert(ret==(b==10?-ETIMEDOUT:0));assert(f.waits==(b==10?9:b));assert(f.writes==2);cases++;}
  f=fresh(ops[i],ins[i]);f.initial_busy=true;assert(apple_nhi_m1_query(rd,wr,wt,&f,f.op,f.input)==-EBUSY);assert(!f.writes&&f.calls==1);cases++;
  for(unsigned st=1;st<64;st++){f=fresh(ops[i],ins[i]);f.complete|=st<<24;assert(apple_nhi_m1_query(rd,wr,wt,&f,f.op,f.input)==((st==2&&f.op==0x25)?-EOPNOTSUPP:-EIO));assert(f.calls==4);cases++;}
  f=fresh(ops[i],ins[i]);f.complete|=1U<<30;assert(apple_nhi_m1_query(rd,wr,wt,&f,f.op,f.input)==-EOPNOTSUPP);assert(f.calls==4);cases++;
 }
 for(unsigned op=0;op<256;op++)for(unsigned in=0;in<8;in++) {
  if(((op==0x25||op==0x33)&&in==0)||(op==0x10&&(in==5||in==6)))continue;
  struct fake f=fresh(op,in);assert(apple_nhi_m1_query(rd,wr,wt,&f,op,in)==-EINVAL);assert(!f.calls);cases++;
 }
 for(unsigned k=0;k<3;k++){struct fake f=fresh(0x25,0);assert(apple_nhi_m1_query(k==0?NULL:rd,k==1?NULL:wr,k==2?NULL:wt,&f,0x25,0)==-EINVAL);assert(!f.calls);cases++;}
 for(unsigned len=17;len<256;len++){struct fake f=fresh(0x33,0);f.result=len;assert(apple_nhi_m1_query(rd,wr,wt,&f,0x33,0)==-EMSGSIZE);assert(f.calls==5);cases++;}
 printf("QUERY FAULT TESTS: %u cases, zero failures\n",cases);
}
