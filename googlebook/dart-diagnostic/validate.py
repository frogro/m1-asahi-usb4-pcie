from pathlib import Path
import sys,json,hashlib,subprocess as s,tempfile,os
mode,a,b=sys.argv[1:]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
if mode=='config':
 def cfg(p):return {l.split('=',1)[0]:l.split('=',1)[1] for l in Path(p).read_text().splitlines() if l.startswith('CONFIG_') and '=' in l}
 x,y=cfg(a),cfg(b); allowed={'CONFIG_CC_VERSION_TEXT','CONFIG_GCC_VERSION','CONFIG_AS_VERSION','CONFIG_LD_VERSION','CONFIG_PAHOLE_VERSION','CONFIG_RUSTC_VERSION_TEXT','CONFIG_RUSTC_VERSION','CONFIG_RUSTC_LLVM_VERSION','CONFIG_RUSTC_LLVM_MAJOR_VERSION'}
 diff={k:[x.get(k),y.get(k)] for k in x.keys()|y.keys() if x.get(k)!=y.get(k)}
 assert not (diff.keys()-allowed),diff
 print('Config differences:',json.dumps(diff))
elif mode=='source':
 m=json.loads(Path(b).read_text());assert sha(Path(a))==m['original_sha256']
elif mode=='modules':
 d=Path(a);m=json.loads(Path(b).read_text());res={}
 for n in ['baseline','candidate']:
  p=d/f'apple-dart-{n}.ko'
  vermagic=s.check_output(['modinfo','-F','vermagic',str(p)],text=True).strip()
  assert vermagic==m['expected_vermagic'],vermagic
  deps=s.check_output(['modinfo','-F','depends',str(p)],text=True).strip()
  imports=sorted(l.split()[-1] for l in s.check_output([os.environ.get('CROSS_COMPILE','')+'nm','-u',str(p)],text=True).splitlines())
  with tempfile.TemporaryDirectory() as t:
   sec=Path(t)/'text';s.run([os.environ.get('CROSS_COMPILE','')+'objcopy','--dump-section','.text='+str(sec),str(p),os.devnull],check=True);text_sha=sha(sec)
  res[n]={'sha256':sha(p),'text_sha256':text_sha,'vermagic':vermagic,'depends':deps,'imports':imports}
 assert res['baseline']['text_sha256']==m['original_text_sha256'], 'Baseline machine code differs; stop deployment'
 assert res['baseline']['depends']==m['expected_depends']==res['candidate']['depends']
 # Logging may introduce its own symbol; all other imports must match.
 assert set(res['candidate']['imports'])-set(res['baseline']['imports']) <= {'_printk','param_ops_bool'},res
 assert 'legacy_locked_ttbr:bool' in s.check_output(['modinfo','-p',str(d/'apple-dart-candidate.ko')],text=True)
 res['passed']=True
 (d/'dart-validation.json').write_text(json.dumps(res,indent=2)+'\n')
 print('DART baseline reproduction and candidate ABI checks passed')
else:raise RuntimeError(mode)
