from pathlib import Path
import subprocess,json,sys,tempfile,hashlib
p=Path(__file__).resolve().parent
prefix=r'''
#include <assert.h>
#include <errno.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
struct mutex { int locked; };
static void mutex_lock(struct mutex *m) { assert(!m->locked); m->locked=1; }
static void mutex_unlock(struct mutex *m) { assert(m->locked); m->locked=0; }
struct dcp_audio { struct mutex data_lock; int connected,open_cookie,connection_cookie; void *chan; };
struct snd_dmaengine_dai_dma_data { int flags; };
struct snd_pcm_hardware { unsigned long info,periods_min,periods_max,period_bytes_min,period_bytes_max,buffer_bytes_max,fifo_size; };
struct runtime { struct snd_pcm_hardware hw; };
struct pcm { void *private_data; };
struct snd_pcm_substream { struct pcm *pcm; struct runtime *runtime; };
static struct snd_pcm_hardware dcp_pcm_hw;
static int dma_result, remote_result, refine_result, open_result;
static int dcpaud_init_dma(struct dcp_audio *d) { (void)d; return dma_result; }
static int dcpaud_read_remote_info(struct dcp_audio *d) { assert(!d->data_lock.locked); return remote_result; }
#define SND_DMAENGINE_PCM_DAI_FLAG_PACK 1
#define SNDRV_PCM_INFO_MMAP 1
#define SNDRV_PCM_INFO_MMAP_VALID 2
#define SNDRV_PCM_INFO_INTERLEAVED 4
#define snd_pcm_hw_rule_add(...) ((void)0)
#define snd_dmaengine_pcm_refine_runtime_hwparams(...) (refine_result)
#define snd_dmaengine_pcm_open(...) (open_result)
'''
suffix=r'''
int main(void) {
 int values[]={-ENXIO,-EIO,-ENOMEM,-517,0};
 int failures=0,cases=0;
 for(unsigned i=0;i<sizeof(values)/sizeof(values[0]);i++)
 for(int connected=0;connected<2;connected++) {
  struct dcp_audio a={.connected=connected,.connection_cookie=9};
  struct pcm pcm={.private_data=&a}; struct runtime r={0};
  struct snd_pcm_substream sub={.pcm=&pcm,.runtime=&r};
  dma_result=values[i];remote_result=refine_result=open_result=0;
  int result=dcp_pcm_open(&sub);
  int expected=dma_result<0?dma_result:(connected?0:-ENXIO);
  assert(result==expected);cases++;
  if(a.data_lock.locked) {failures++;continue;}
  /* A successful later retry must remain possible after the failed open. */
  dma_result=0;a.connected=1;
  assert(dcp_pcm_open(&sub)==0);assert(!a.data_lock.locked);
 }
 for(int stage=0;stage<3;stage++) {
  struct dcp_audio a={.connected=1};struct pcm pcm={.private_data=&a};
  struct runtime r={0};struct snd_pcm_substream sub={.pcm=&pcm,.runtime=&r};
  dma_result=remote_result=refine_result=open_result=0;
  if(stage==0)remote_result=-EIO;
  if(stage==1)refine_result=-EINVAL;
  if(stage==2)open_result=-EBUSY;
  assert(dcp_pcm_open(&sub)<0);assert(!a.data_lock.locked);cases++;
 }
 printf("cases=%d lock_leaks=%d\n",cases,failures);
 return failures?1:0;
}
'''
if len(sys.argv)!=2:
 raise SystemExit('Usage: test-open.py /path/to/linux/drivers/gpu/drm/apple/audio.c')
original=Path(sys.argv[1]).read_text()
expected=json.loads((p/'provenance.json').read_text())['source_sha256']
assert hashlib.sha256(original.encode()).hexdigest()==expected
with tempfile.TemporaryDirectory(prefix='dcp-audio-patch-') as tmp:
 root=Path(tmp); target=root/'drivers/gpu/drm/apple/audio.c';target.parent.mkdir(parents=True);target.write_text(original)
 subprocess.run(['patch','--batch','--fuzz=0','-p1','-i',str(p/'0001-drm-apple-release-audio-lock-on-DMA-error.patch')],cwd=root,check=True)
 inputs={'original':original,'fixed':target.read_text()}
results={}
for name in ('original','fixed'):
 s=inputs[name];start=s.index('static int dcp_pcm_open(');end=s.index('static int dcp_pcm_close(',start)
 c=p/f'test-{name}.c';c.write_text(prefix+s[start:end]+suffix)
 exe=p/f'test-{name}'
 subprocess.run(['cc','-Wall','-Wextra','-Wno-unused-variable','-fsanitize=undefined','-g',str(c),'-o',str(exe)],check=True)
 r=subprocess.run([str(exe)],capture_output=True,text=True)
 results[name]={'exit':r.returncode,'output':r.stdout,'stderr':r.stderr}
assert results['original']['exit']==1
assert results['fixed']['exit']==0
(p/'tests.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(results,indent=2))
