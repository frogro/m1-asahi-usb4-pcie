from pathlib import Path
import subprocess,json
r=Path(__file__).parent;s=r/'source'
body=(s/'cmd/apple_nhi_m1_inventory.c').read_text().split('int apple_nhi_m1_query(',1)[1].split('/* USB4 v1, single-hop router setup',1)[0]
pre='''#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdbool.h>
#include <string.h>
#include <errno.h>
#include <assert.h>
typedef uint32_t u32;
typedef int (*apple_nhi_read_fn)(void *,unsigned,unsigned,unsigned,unsigned,u32*);
typedef int (*apple_nhi_tmu_write_fn)(void *,unsigned,u32);
'''
post=r'''
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
'''
(r/'query-test.c').write_text(pre+'int apple_nhi_m1_query('+body+post)
subprocess.run(['gcc','-std=c11','-O1','-g','-fsanitize=address,undefined','-Wall','-Wextra','-Werror',str(r/'query-test.c'),'-o',str(r/'query-test')],check=True)
p=subprocess.run([str(r/'query-test')],capture_output=True,text=True);(r/'query-test.log').write_text(p.stdout+p.stderr);assert p.returncode==0,p.stderr;print(p.stdout.splitlines()[-1])

(r/"query-result-v12.json").write_text(json.dumps({"passed":True,"summary":p.stdout.splitlines()[-1],"ASan":True,"UBSan":True},indent=2)+"\n")
