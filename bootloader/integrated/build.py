#!/usr/bin/env python3
"""Reconstruct the integrated U-Boot source and build/check it. Never installs."""
import argparse,hashlib,json,os,re,shutil,subprocess
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('source',type=Path);p.add_argument('output',type=Path);p.add_argument('--jobs',type=int,default=4)
a=p.parse_args();here=Path(__file__).resolve().parent;m=json.loads((here/'manifest.json').read_text())
if not 1<=a.jobs<=32:p.error('jobs must be between 1 and 32')
src=a.source.resolve();out=a.output.resolve()
for patch in m['patches']:
 if hashlib.sha256((here/patch['file']).read_bytes()).hexdigest()!=patch['sha256']:raise SystemExit('Patch digest mismatch: '+patch['file'])
subprocess.run(['git','-C',str(src),'cat-file','-e',m['base_commit']+'^{commit}'],check=True)
out.mkdir(parents=True,exist_ok=False);work=out/'source';env=os.environ.copy();env['SDL_VIDEODRIVER']='dummy';env.pop('CROSS_COMPILE',None)
(out/'tmp').mkdir();env['TMPDIR']=str(out/'tmp')
env['SOURCE_DATE_EPOCH']=subprocess.check_output(['git','-C',str(src),'show','-s','--format=%ct',m['base_commit']],text=True).strip()
def run(args,log,cwd=None):
 with (out/log).open('w') as f:subprocess.run([str(x) for x in args],cwd=cwd or work,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
run(['git','-C',src,'worktree','add','--detach',work,m['base_commit']],'worktree.log',src)
for i,patch in enumerate(m['patches']):
 run(['git','apply','--check',here/patch['file']],f'patch-{i}-check.log')
 run(['git','apply',here/patch['file']],f'patch-{i}.log')
run(['git','diff','--check'],'diff-check.log')
for profile in ['apple','sandbox']:
 build=out/profile;build.mkdir();shutil.copyfile(here/(profile+'.config'),build/'.config')
 cmd=['make',f'O={build}']+(['CROSS_COMPILE=aarch64-linux-gnu-'] if profile=='apple' else [])
 run(cmd+['olddefconfig'],profile+'-config.log');run(cmd+[f'-j{a.jobs}'],profile+'-build.log')
required=['NVME_APPLE','NVME_PCI','USB_STORAGE','CMD_BOOTFLOW','BOOTMETH_EFILOADER','CMD_APPLE_ATC_M1','EFI_VARIABLE_NO_STORE']
config=(out/'apple/.config').read_text()
for key in required:
 if f'CONFIG_{key}=y\n' not in config:raise SystemExit('Missing feature '+key)
results={}
for pattern in ['apple_dart','iommu','pci','apple_mbox','usb4_cfg','apple_i2c','cd321x','atc_m1','pciec_m1']:
 log='test-'+pattern+'.log';run([out/'sandbox/u-boot','-T','-c','ut dm '+pattern+'*'],log,out/'sandbox')
 match=re.search(r'Tests run: (\d+),.*failures: (\d+)',(out/log).read_text())
 if not match or int(match[2]) or not int(match[1]):raise SystemExit('Test failed: '+pattern)
 results[pattern]=int(match[1])
run(['dtc','-I','dts','-O','dtb','-o',out/'j274-integrated.dtb',here/'j274-integrated.dts'],'dtc.log')
run(['python3',here/'test-integration.py',work,out/'j274-integrated.dtb',out/'policy-tests'],'policy-tests.log')
run(['python3',here/'test-usb4.py',work,out/'usb4-tests'],'usb4-tests.log')
run(['python3',here/'test-root-auth.py',out/'root-auth-tests'],'root-auth-tests.log')
run(['python3',here/'test-xhci-handover.py',work,out/'xhci-handover-tests'],'xhci-handover-tests.log')
result={'manifest':m,'software_tests':results,'installed':False,'uboot_sha256':hashlib.sha256((out/'apple/u-boot-nodtb.bin').read_bytes()).hexdigest()}
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
