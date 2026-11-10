#!/usr/bin/env python3
"""Exercise actual fscrypt bio setup/merge functions with stub crypto operations."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('source',type=Path)
p.add_argument('--before-dir',required=True,type=Path)
p.add_argument('--output',required=True,type=Path)
a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
m=json.loads((Path(__file__).parent/'manifest.json').read_text())
block='fs/crypto/block.c';header='include/linux/fscrypt.h'
for root,group,names in [(a.source,'postimages',[block,header]),(a.before_dir,'preimages',[block])]:
 for name in names:
  assert hashlib.sha256((root/name).read_bytes()).hexdigest()==m[group][name],name

def function(s,marker):
 start=s.index(marker);end=s.index('{',start)+1;depth=1
 while depth:
  depth+=(s[end]=='{')-(s[end]=='}');end+=1
 return s[start:end]

h=(a.source/header).read_text()
helpers=function(h,'static inline bool fscrypt_needs_contents_encryption(')+'\n'+function(h,'static inline bool\nfscrypt_inode_should_skip_dm_default_key(')
prefix=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
typedef uint64_t u64;
typedef int64_t loff_t;
typedef int gfp_t;
#define BLK_CRYPTO_DUN_ARRAY_SIZE 4
#define IS_ENCRYPTED(i) ((i)->encrypted)
#define S_ISREG(m) ((m)==1)
struct key { int id; };
struct fscrypt_inode_info { struct { struct key *blk_key; } ci_enc_key; };
struct inode { bool encrypted; int i_mode; struct fscrypt_inode_info ci; };
struct bio_crypt_ctx { const struct key *bc_key; u64 dun; };
struct bio { struct bio_crypt_ctx *bi_crypt_context,storage;
 struct { unsigned bi_size; } bi_iter; bool skip; };
static const struct fscrypt_inode_info *fscrypt_get_inode_info_raw(const struct inode *i) { return &i->ci; }
static void fscrypt_generate_dun(const struct fscrypt_inode_info *ci,loff_t pos,u64 *dun) {
 (void)ci;dun[0]=pos/4096;
}
static void bio_crypt_set_ctx(struct bio *b,const struct key *k,u64 *dun,gfp_t g) {
 (void)g;b->storage.bc_key=k;b->storage.dun=dun[0];b->bi_crypt_context=&b->storage;
}
static bool bio_crypt_dun_is_contiguous(const struct bio_crypt_ctx *c,unsigned size,u64 *dun) {
 return c->dun+size/4096==dun[0];
}
static void bio_set_skip_dm_default_key(struct bio *b) { b->skip=true; }
static bool bio_should_skip_dm_default_key(struct bio *b) { return b->skip; }
'''
suffix=r'''
int main(void) {
 struct key keys[2]={{0},{1}};int cases=0,failures=0;
 for(int enc=0;enc<2;enc++) for(int mode=0;mode<3;mode++) {
  struct inode first={.encrypted=enc,.i_mode=mode,.ci={.ci_enc_key={.blk_key=&keys[0]}}};
  struct bio bio={.bi_iter={.bi_size=4096}};
  bool contents=enc && mode==1;
  fscrypt_set_bio_crypt_ctx(&bio,&first,0,0);
  assert(!!bio.bi_crypt_context==contents);
  cases++;if(bio.skip!=contents)failures++;
  for(int enc2=0;enc2<2;enc2++) for(int mode2=0;mode2<3;mode2++)
  for(int different_key=0;different_key<2;different_key++)
  for(int gap=0;gap<2;gap++) for(int flag=0;flag<2;flag++) {
   struct inode next={.encrypted=enc2,.i_mode=mode2,
    .ci={.ci_enc_key={.blk_key=&keys[different_key]}}};
   bool next_contents=enc2 && mode2==1;
   bio.skip=flag;
   bool expected=(contents==next_contents && flag==next_contents &&
                  (!contents || (!different_key && !gap)));
   bool actual=fscrypt_mergeable_bio(&bio,&next,gap?8192:4096);
   cases++;if(actual!=expected)failures++;
  }
 }
 printf("cases=%d policy_failures=%d\n",cases,failures);
 return failures?1:0;
}
'''
results={}
for name,root in [('before',a.before_dir),('after',a.source)]:
 s=(root/block).read_text()
 body='\n'.join(function(s,marker) for marker in ['void fscrypt_set_bio_crypt_ctx(', 'bool fscrypt_mergeable_bio('])
 code=prefix+helpers+body+suffix;src=a.output/(name+'.c');src.write_text(code);exe=a.output/name
 subprocess.run(['cc','-std=gnu11','-Wall','-Wextra','-Wno-unused-function','-Werror',
                 '-fsanitize=undefined','-fno-sanitize-recover=all',str(src),'-o',str(exe)],check=True)
 r=subprocess.run([str(exe.resolve())],text=True,capture_output=True)
 results[name]={'exit':r.returncode,'stdout':r.stdout,'stderr':r.stderr,
                'harness_sha256':hashlib.sha256(code.encode()).hexdigest()}
 assert r.returncode==(1 if name=='before' else 0) and not r.stderr,results[name]
(a.output/'results.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps(results,indent=2))
