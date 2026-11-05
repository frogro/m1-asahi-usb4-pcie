#!/usr/bin/env python3
"""Build local EROFS module images from an unpacked matching kernel package."""
import argparse,hashlib,json,re,shlex,shutil,subprocess
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('kernel_root',type=Path);p.add_argument('firmware',type=Path);p.add_argument('output',type=Path)
p.add_argument('--release',required=True);p.add_argument('--mkfs',default='mkfs.erofs');p.add_argument('--fsck',default='fsck.erofs')
a=p.parse_args();release=a.release
if not re.fullmatch(r'[A-Za-z0-9._+-]+',release):raise SystemExit('Invalid release')
root=a.kernel_root.resolve();out=a.output.resolve();here=Path(__file__).resolve().parent
if out.exists():raise SystemExit('Output must be new')
config=dict(re.findall(r'^(CONFIG_\w+)=(.*)$',(root/'boot'/('config-'+release)).read_text(),re.M))
for key in ['EROFS_FS','BLK_DEV_LOOP','BLK_DEV_INITRD','RD_GZIP']:
 if config.get('CONFIG_'+key)!='y':raise SystemExit('Missing built-in '+key)
if not (a.firmware/'apple/avd-fw-v2-t0.bin').is_file():raise SystemExit('Supply the complete matched local firmware tree, including Apple AVD')
out.mkdir(parents=True);stage=out/'stage';mods=stage/'lib/modules'/release
shutil.copytree(root/'lib/modules'/release,mods,symlinks=True)
for n in ['build','source']:
 if (mods/n).is_symlink():(mods/n).unlink()
for suffix,tool in [('.zst','zstd'),('.xz','xz')]:
 for m in mods.rglob('*.ko'+suffix):
  with m.with_suffix('').open('xb') as dst:subprocess.run([tool,'-dc',str(m)],stdout=dst,check=True)
  m.unlink()
for m in mods.glob('modules.*'):
 if m.name not in ['modules.builtin','modules.builtin.modinfo','modules.order'] and m.is_file():m.unlink()
with (out/'depmod-errors.txt').open('w') as err:
 subprocess.run(['depmod','-b',str(stage),'-e','-F',str(root/'boot'/('System.map-'+release)),release],stderr=err,check=True)
if (out/'depmod-errors.txt').read_text().strip():raise SystemExit('depmod reported errors')
files=list(mods.rglob('*.ko'))
if not files:raise SystemExit('No modules')
for m in files:
 if subprocess.check_output(['modinfo','-F','vermagic',str(m)],text=True).split()[0]!=release:raise SystemExit('ABI mismatch '+str(m))
vendor=out/'vendor-tree';dest=vendor/'lib/modules';shutil.copytree(mods,dest,symlinks=True)
(dest/'modules.load').write_text('')
soft=dest/'modules.softdep';soft.write_text(soft.read_text()+'\nsoftdep brcmfmac post: brcmfmac-wcc\n')
shutil.copytree(a.firmware,dest/'firmware',symlinks=True)
# Re-resolve the known required module set against this new kernel's dependency graph.
requested=re.findall(r'load_module\("/m1-modulefs/lib/modules/([^\"]+)\.ko", ([01])\);',(here/'preload.inc').read_text())
ordered={}
for rel,optional in requested:
 name=Path(rel).name
 result=subprocess.run(['modprobe','-C','/dev/null','-d',str(stage),'-S',release,'--show-depends',name],capture_output=True,text=True,check=True)
 for line in result.stdout.splitlines():
  if line.startswith('insmod '):
   path=Path(shlex.split(line)[1]);key=str(path.relative_to(mods))
   if not (dest/key).is_file():raise SystemExit('Missing dependency '+key)
   ordered[key]=min(ordered.get(key,1),int(optional))
(out/'preload.inc').write_text(''.join(f'load_module("/m1-modulefs/lib/modules/{key}", {opt});\n' for key,opt in ordered.items()))
contexts=out/'file_contexts';contexts.write_text('/vendor_dlkm(/.*)? u:object_r:vendor_file:s0\n/vendor_dlkm/lib/modules/.*\\.ko u:object_r:vendor_kernel_modules:s0\n/vendor_dlkm/lib/modules/firmware(/.*)? u:object_r:vendor_firmware_file:s0\n/system_dlkm(/.*)? u:object_r:system_file:s0\n')
system=out/'system-tree';(system/'lib/modules').mkdir(parents=True)
images={}
for name,tree in [('vendor',vendor),('system',system)]:
 image=out/(name+'_dlkm.erofs')
 subprocess.run([a.mkfs,'-zlz4hc','-T1230768000','--all-root','--mount-point=/'+name+'_dlkm','--file-contexts='+str(contexts),str(image),str(tree)],check=True)
 subprocess.run([a.fsck,str(image)],check=True)
 images[name+'_dlkm']=hashlib.file_digest(image.open('rb'),'sha256').hexdigest()
(out/'module-images.json').write_text(json.dumps({'release':release,'modules':len(files),'sha256':images,'local_only':True,'installed':False},indent=2)+'\n')
print('Local module images prepared; no installation performed')
