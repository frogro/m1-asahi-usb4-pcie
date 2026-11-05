#!/usr/bin/env python3
"""Local-only rebuild of a prepared Googlebook ramdisk; never installs or uploads."""
import argparse,gzip,hashlib,json,re,stat,subprocess,tempfile,uuid
from pathlib import Path
from newc import read_newc,write_newc
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('profile',type=Path);p.add_argument('base',type=Path);p.add_argument('vendor_dlkm',type=Path);p.add_argument('system_dlkm',type=Path);p.add_argument('output',type=Path);p.add_argument('--cc',default='aarch64-linux-gnu-gcc');p.add_argument('--preload',type=Path)
a=p.parse_args();cfg=json.loads(a.profile.read_text());here=Path(__file__).resolve().parent
if a.output.exists():raise SystemExit('Output must not exist')
release=cfg['kernel_release']
if not re.fullmatch(r'[A-Za-z0-9._+-]+',release):raise SystemExit('Invalid kernel release')
for key in ['selected_router','selected_super','selected_dock']:cfg[key]=str(uuid.UUID(cfg[key]))
inputs={}
for name,path in [('base',a.base),('vendor_dlkm',a.vendor_dlkm),('system_dlkm',a.system_dlkm)]:
 data=path.read_bytes();digest=hashlib.sha256(data).hexdigest()
 if digest!=cfg['sha256'][name]:raise SystemExit('Input hash mismatch: '+name)
 inputs[name]=data
records=read_newc(gzip.decompress(inputs['base']))
names=[n for n,f,b in records]
if len(set(names))!=len(names):raise SystemExit('Duplicate archive names')
required=['init','m1-bootstrap','first_stage_ramdisk/fstab.android-desktop','googlebook-vendor_dlkm.erofs','googlebook-system_dlkm.erofs']
if any(names.count(n)!=1 for n in required):raise SystemExit('Expected prepared M1 Android ramdisk')
fstab=next(b for n,f,b in records if n=='first_stage_ramdisk/fstab.android-desktop')
if not all(x in fstab for x in [b'GBOOK_VENDOR_LOOP',b'GBOOK_SYSTEM_LOOP']):raise SystemExit('Expected loop module placeholders')
with tempfile.TemporaryDirectory() as temp:
 work=Path(temp)
 for name in ['bootstrap.c','root-access.h','preload.inc']:(work/name).write_bytes((a.preload if name=='preload.inc' and a.preload else here/name).read_bytes())
 (work/'profile.h').write_text('\n'.join('#define '+macro+' '+json.dumps(cfg[key]) for macro,key in [('SELECTED_ROUTER','selected_router'),('SELECTED_SUPER','selected_super'),('SELECTED_DOCK','selected_dock')])+'\n')
 subprocess.run([a.cc,'-static','-O2','-Wall','-Wextra','-DEXPECTED_RELEASE='+json.dumps(release),str(work/'bootstrap.c'),'-o',str(work/'bootstrap')],check=True)
 # Validate every module in the replacement EROFS using the target ABI.
 module_count=0
 for name in ['vendor_dlkm','system_dlkm']:
  image=work/(name+'.erofs');image.write_bytes(inputs[name]);tree=work/name
  subprocess.run(['fsck.erofs','--extract='+str(tree),str(image)],check=True,stdout=subprocess.DEVNULL)
  for module in tree.rglob('*.ko'):
   vermagic=subprocess.check_output(['modinfo','-F','vermagic',str(module)],text=True).split()[0]
   if vermagic!=release:raise SystemExit('Module ABI mismatch: '+str(module))
   module_count+=1
  if name=='vendor_dlkm':
   for rel in re.findall(r'load_module\("/m1-modulefs/([^\"]+)',(work/'preload.inc').read_text()):
    if not (tree/rel).is_file():raise SystemExit('Missing preload module: '+rel)
 if not module_count:raise SystemExit('Empty module images')
 replacements={'m1-bootstrap':(work/'bootstrap').read_bytes(),'googlebook-vendor_dlkm.erofs':inputs['vendor_dlkm'],'googlebook-system_dlkm.erofs':inputs['system_dlkm']}
 for n,f,b in records:
  if n in replacements and (not stat.S_ISREG(f[1]) or f[4]!=1):raise SystemExit('Replacement must be a non-hardlinked regular file: '+n)
 updated=[(n,f,replacements.get(n,b)) for n,f,b in records]
 raw=write_newc(updated);checked=read_newc(raw)
 if [(n,f[:6]+f[7:11],b) for n,f,b in updated]!=[(n,f[:6]+f[7:11],b) for n,f,b in checked]:raise SystemExit('CPIO metadata roundtrip failed')
 result=gzip.compress(raw,compresslevel=6,mtime=0)
 with a.output.open('xb') as out:out.write(result)
 report={'sha256':hashlib.sha256(result).hexdigest(),'kernel_release':release,'module_count':module_count,'changed_paths':list(replacements),'local_only':True,'installed':False,'hardware_validated':False}
 a.output.with_suffix(a.output.suffix+'.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(report))
