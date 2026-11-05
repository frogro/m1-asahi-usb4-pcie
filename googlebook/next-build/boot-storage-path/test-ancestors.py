from pathlib import Path
import subprocess
import argparse
p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);args=p.parse_args()
w=args.output;w.mkdir(parents=True,exist_ok=True)
s=args.source.read_text()
a=s.index('static bool tb_switch_on_protected_boot_path(');b=s.index('\nstatic int tb_switch_set_authorized',a)
helper=s[a:b]
source=r'''
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <assert.h>
typedef int uuid_t;
struct tb {int id;};
struct tb_switch {struct tb *tb;struct tb_switch *parent; unsigned long long route; int uuid; bool authorized;};
static char boot_protect_uuid[40];
static struct tb_switch nodes[20];
static int count,gets,puts,checks;
static int uuid_parse(const char *s,uuid_t *id) {if(strcmp(s,"selected"))return -1;*id=42;return 0;}
static unsigned long long tb_route(struct tb_switch *s) {return s->route;}
static struct tb_switch *tb_switch_parent(struct tb_switch *s) {return s->parent;}
static struct tb_switch *tb_switch_find_by_uuid(struct tb *tb,uuid_t *id) {for(int i=0;i<count;i++)if(nodes[i].tb==tb && nodes[i].uuid==*id){gets++;return &nodes[i];}return NULL;}
static void tb_switch_put(struct tb_switch *s) {assert(s);puts++;}
'''.replace('puts','putcount')+helper+r'''
static void check(int i,bool expected) {bool got=tb_switch_on_protected_boot_path(&nodes[i]);assert(got==expected);assert(gets==putcount);checks++;}
int main(void){
 struct tb domain={1},other={2};
 strcpy(boot_protect_uuid,"selected");
 for(int depth=1;depth<=6;depth++){
  memset(nodes,0,sizeof(nodes));count=depth+4;
  nodes[0]=(struct tb_switch){&domain,NULL,0,1,true};
  for(int i=1;i<=depth;i++)nodes[i]=(struct tb_switch){&domain,&nodes[i-1],i,i==depth?42:10+i,true};
  nodes[depth+1]=(struct tb_switch){&domain,&nodes[0],90,99,true};
  nodes[depth+2]=(struct tb_switch){&domain,&nodes[depth],91,98,true};
  nodes[depth+3]=(struct tb_switch){&other,NULL,1,97,true};
  for(int i=0;i<count;i++)check(i,i>0 && i<=depth);
  nodes[depth].authorized=false;for(int i=0;i<count;i++)check(i,false);nodes[depth].authorized=true;
  boot_protect_uuid[0]=0;for(int i=0;i<count;i++)check(i,false);
  strcpy(boot_protect_uuid,"invalid");for(int i=0;i<count;i++)check(i,false);
  strcpy(boot_protect_uuid,"selected");nodes[depth].uuid=43;for(int i=0;i<count;i++)check(i,false);
 }
 printf("PASS %d topology/authorization/parameter/reference checks\n",checks);
}
'''
(w/'test-ancestors.c').write_text(source)
subprocess.run(['cc','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-g',str(w/'test-ancestors.c'),'-o',str(w/'test-ancestors')],check=True)
subprocess.run([str(w/'test-ancestors')],check=True)
