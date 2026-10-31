#!/usr/bin/env python3
"""Read-only audit of the documented M1 integrated eGPU test prerequisites."""
import json, os, shlex
from pathlib import Path

def read(p):
 try: return Path(p).read_text().strip()
 except (OSError,UnicodeError): return None

def check(name,ok,actual):
 checks.append({'check':name,'passed':bool(ok),'actual':actual})

checks=[]
release=os.uname().release
cmdline=shlex.split(read('/proc/cmdline') or '')
pci=set()
for arg in cmdline:
 if arg.startswith('pci='):pci.update(arg[4:].split(','))
required={'hpbussize=16','hpmmiosize=32M','hpmmioprefsize=512M','realloc=on'}
check('tested PCI reservation/reallocation arguments',required<=pci,sorted(pci))
for name,value in [('runpm','0'),('aspm','0'),('rebar','0')]:
 actual=read('/sys/module/amdgpu/parameters/'+name)
 check('amdgpu '+name,actual==value,actual)
check('global TTM override absent',not Path('/sys/module/ttm/parameters/nonposted_test').exists(),None)
gpus=[]
for dev in Path('/sys/bus/pci/devices').glob('*'):
 if read(dev/'vendor')!='0x1002' or not (read(dev/'class') or '').startswith('0x03'):continue
 funcs=[]
 for f in range(4):
  p=dev.with_name(dev.name[:-1]+str(f))
  if not p.exists():continue
  driver=(p/'driver').resolve().name if (p/'driver').exists() else None
  funcs.append({'pci':p.name,'driver':driver,'runtime_control':read(p/'power/control'),'msi_vectors':len(list((p/'msi_irqs').glob('*')))})
 resources=[]
 for i,line in enumerate((read(dev/'resource') or '').splitlines()[:6]):
  start,end,flags=(int(v,16) for v in line.split())
  if flags & 0x200:
   resources.append({'bar':i,'start':hex(start),'end':hex(end),'nonposted':bool(flags & 0x80)})
   check(dev.name+' memory BAR '+str(i)+' assigned',start>0,hex(start))
   check(dev.name+' memory BAR '+str(i)+' nonposted',bool(flags & 0x80),hex(flags))
 check(dev.name+' AMDGPU bound',(dev/'driver').exists() and (dev/'driver').resolve().name=='amdgpu',funcs)
 if read(dev/'device')=='0x73bf':
  expected=['amdgpu','snd_hda_intel','xhci_hcd','i2c-designware-pci']
  check(dev.name+' all four Navi21 drivers bound',[f['driver'] for f in funcs]==expected,[f['driver'] for f in funcs])
 gpus.append({'pci':dev.name,'device':read(dev/'device'),'functions':funcs,'memory_resources':resources})
check('AMD display device found',bool(gpus),len(gpus))
report={'kernel':release,'boot_id':read('/proc/sys/kernel/random/boot_id'),'checks':checks,'gpus':gpus,'failed':sum(not c['passed'] for c in checks),'limitations':['This is a read-only prerequisite inventory, not a hardware functional test.','Release naming does not prove native patch43 is loaded; verify the installed build artifact separately.','The prefetch register is a strobe, not a readable enabled-state flag.','Physical hotplug tests historically used I2C power/control=on; auto is not equivalent coverage.','External-root initramfs authorization/reprobe hooks are deployment-specific.']}
print(json.dumps(report,indent=2))
raise SystemExit(1 if report['failed'] else 0)
