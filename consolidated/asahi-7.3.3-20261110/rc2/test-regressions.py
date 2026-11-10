#!/usr/bin/env python3
"""Compile actual VM accounting functions and DM teardown ordering in host harnesses.
The mocked environment checks accounting/ordering, not hardware or concurrency.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('before', type=Path)
p.add_argument('after', type=Path)
p.add_argument('--output', required=True, type=Path)
a = p.parse_args()
a.output.mkdir(parents=True, exist_ok=True)
manifest = json.loads((Path(__file__).parent / 'manifest.json').read_text())
for root, key in [(a.before, 'preimages'), (a.after, 'postimages')]:
    for name, expected in manifest[key].items():
        actual = hashlib.sha256((root / name).read_bytes()).hexdigest()
        if actual != expected:
            raise SystemExit('Test input hash mismatch: ' + str(root / name))
VM = 'drivers/gpu/drm/amd/amdgpu/amdgpu_vm'
DM = 'drivers/gpu/drm/amd/display/amdgpu_dm/amdgpu_dm.c'

def extract(text, marker):
    start = text.index(marker)
    pos = text.index('{', start)
    depth = 1
    end = pos + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]

prefix = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#define __AMDGPU_PL_NUM 3
#define AMDGPU_GEM_CREATE_DISCARDABLE 1
struct list_head { void *next, *prev; };
struct ttm_resource { uint32_t mem_type; };
struct gem { bool shared; void *resv; };
struct amdgpu_bo {
 struct { struct gem base; struct ttm_resource *resource; } tbo;
 uint32_t preferred_domains, flags;
 uint64_t size;
};
struct amdgpu_vm {
 struct { struct { uint64_t shared, private, resident, purgeable; } drm;
          uint64_t evicted; } stats[__AMDGPU_PL_NUM];
 int stats_lock;
};
static void spin_lock(int *l) { assert(!*l); *l=1; }
static void spin_unlock(int *l) { assert(*l); *l=0; }
static void dma_resv_assert_held(void *r) { (void)r; }
static bool drm_gem_object_is_shared_for_memory_stats(struct gem *g) { return g->shared; }
static uint64_t amdgpu_bo_size(struct amdgpu_bo *b) { return b->size; }
static uint32_t amdgpu_mem_type_to_domain(uint32_t m) { return 1u << m; }
/* CPU/GTT/VRAM subset of the driver's highest-preferred-domain rule. */
static uint32_t amdgpu_bo_mem_stats_placement(struct amdgpu_bo *b) {
 return b->preferred_domains & 4 ? 2 : b->preferred_domains & 2 ? 1 : 0;
}
'''
suffix = r'''
static int nonzero(struct amdgpu_vm *v) {
 for (int i=0;i<__AMDGPU_PL_NUM;i++) {
  if(v->stats[i].drm.shared || v->stats[i].drm.private ||
     v->stats[i].drm.resident || v->stats[i].drm.purgeable ||
     v->stats[i].evicted) return 1;
 }
 return 0;
}
static void update(struct amdgpu_vm_bo_base *b, struct ttm_resource *r, int sign) {
 spin_lock(&b->vm->stats_lock);
 amdgpu_vm_update_stats_locked(b,r,sign);
 spin_unlock(&b->vm->stats_lock);
}
int main(void) {
 int cases=0,failed=0,domain_failed=0,sharing_failed=0,move_failed=0;
 /* Preferred-domain changes with/without residency, moves, sharing and two VMs. */
 for(unsigned old=1;old<=7;old++) for(unsigned now=1;now<=7;now++)
 for(int location=-1;location<=3;location++)
 for(int shared=0;shared<2;shared++) for(int toggle=0;toggle<2;toggle++)
 for(int move=0;move<2;move++) for(int discard=0;discard<2;discard++) {
  struct amdgpu_vm v[2]={0};
  struct ttm_resource r={.mem_type=location}, next={.mem_type=2};
  struct ttm_resource *res=location<0?NULL:&r;
  struct amdgpu_bo bo={.tbo={.base={.shared=shared},.resource=res},
    .preferred_domains=old,.flags=discard,.size=16384};
  struct amdgpu_vm_bo_base b[2]={
    {.vm=&v[0],.bo=&bo,.shared=shared}, {.vm=&v[1],.bo=&bo,.shared=shared}};
  for(int j=0;j<2;j++) {
   update(&b[j],res,1);
   unsigned bucket=amdgpu_bo_mem_stats_placement(&bo);
   assert(v[j].stats[bucket].drm.shared == (shared?bo.size:0));
   assert(v[j].stats[bucket].drm.private == (shared?0:bo.size));
   if(location>=0 && location<__AMDGPU_PL_NUM)
    assert(v[j].stats[location].drm.resident==bo.size);
  }
  bo.preferred_domains=now;
  if(toggle) {
   bo.tbo.base.shared=!shared;
   for(int j=0;j<2;j++) amdgpu_vm_update_shared(&b[j]);
  }
  if(move) {
   for(int j=0;j<2;j++) { update(&b[j],res,-1); update(&b[j],&next,1); }
   res=&next; bo.tbo.resource=res;
   /* A second change after the move exercises refreshed eviction charges. */
   bo.preferred_domains=old;
  }
  for(int j=0;j<2;j++) update(&b[j],res,-1);
  int bad=nonzero(&v[0]) || nonzero(&v[1]);
  assert(!v[0].stats_lock && !v[1].stats_lock);
  cases++; failed+=bad;
  if(bad) { if(move) move_failed++; else if(toggle) sharing_failed++; else domain_failed++; }
 }
 printf("cases=%d unbalanced=%d domain=%d sharing=%d move=%d\n",
        cases,failed,domain_failed,sharing_failed,move_failed);
 return failed?1:0;
}
'''
dm_prefix = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
struct dm { int dc_lock; };
struct amdgpu_device { struct dm dm; bool no_hw_access; };
static int disabled, powered, destroyed, order;
static void amdgpu_dm_ism_disable(struct dm *d) {
 assert(!d->dc_lock && order==0); disabled++; order=1;
}
static void amdgpu_dm_ism_force_full_power(struct dm *d) {
 assert(d->dc_lock && order==1); powered++; order=2;
}
static void amdgpu_dm_destroy_drm_device(struct dm *d) {
 assert(!d->dc_lock && disabled); destroyed++; order=3;
}
#define scoped_guard(type, lock) for(int once=(assert(!*(lock)),*(lock)=1); once; once=0,*(lock)=0)
'''
dm_suffix = r'''
int main(void) {
 int failed=0;
 for(int offline=0;offline<2;offline++) {
  struct amdgpu_device a={.no_hw_access=offline};
  disabled=powered=destroyed=order=0;
  tested_teardown(&a);
  assert(disabled==1 && destroyed==1 && !a.dm.dc_lock && order==3);
  if(powered != !offline) failed++;
 }
 printf("cases=2 invalid_power_requests=%d\n",failed);
 return failed?1:0;
}
'''
results = {}
for label, root in [('before', a.before), ('after', a.after)]:
    c = (root / (VM + '.c')).read_text()
    h = (root / (VM + '.h')).read_text()
    dm = (root / DM).read_text()
    base = extract(h, 'struct amdgpu_vm_bo_base {') + ';\n'
    functions = '\n'.join(extract(c, 'static void ' + f + '(') for f in
                          ['amdgpu_vm_update_shared', 'amdgpu_vm_update_stats_locked'])
    fini = extract(dm, 'static void amdgpu_dm_fini(struct amdgpu_device *adev)\n{')
    begin = fini.index('\tamdgpu_dm_ism_disable(')
    end_marker = '\tamdgpu_dm_destroy_drm_device(&adev->dm);'
    end = fini.index(end_marker, begin) + len(end_marker)
    flow = 'static void tested_teardown(struct amdgpu_device *adev) {\n' + fini[begin:end] + '\n}\n'
    for kind, source in [('vm', prefix + base + functions + suffix),
                         ('dm', dm_prefix + flow + dm_suffix)]:
        key = f'{label}-{kind}'
        path = a.output / (key + '.c')
        exe = a.output / key
        path.write_text(source)
        subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                        '-fsanitize=undefined', '-fno-sanitize-recover=all',
                        str(path), '-o', str(exe)], check=True)
        run = subprocess.run([str(exe.resolve())], text=True, capture_output=True)
        results[key] = {'exit': run.returncode, 'stdout': run.stdout, 'stderr': run.stderr,
                        'harness_sha256': hashlib.sha256(source.encode()).hexdigest()}
        expected = 1 if label == 'before' else 0
        if run.returncode != expected or run.stderr:
            raise SystemExit(f'Unexpected result {key}: {results[key]}')
(a.output / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
print(json.dumps(results, indent=2))
