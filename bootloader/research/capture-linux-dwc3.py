#!/usr/bin/env python3
"""Read fixed DWC3 controls only after driver/runtime-power guards. No MMIO writes."""
from pathlib import Path
import subprocess,json,time,os
assert os.geteuid()==0
assert os.uname().release=='7.2.12-usb4sd4-egpu2'
p=Path('/sys/bus/platform/devices/502280000.usb')
assert (p/'driver').exists()
base=0x502280000
regs=[0xc110,0xc11c,0xc120,0xc12c,0xc140,0xc144,0xc14c,0xc200,0xc2c0,0xc630,0xcd38,0xcd3c,0xcd40]
def read(a):
 return int(subprocess.check_output(['busybox','devmem',hex(a),'32'],text=True,timeout=3).strip(),16)
def guard():
 assert (p/'power/runtime_status').read_text().strip()=='active'
 v=read(0x23d2800a0)
 assert v!=0xffffffff and v&255==255 and not v&((1<<31)|(1<<10)),hex(v)
guard()
id=read(base+0xc120)
assert id&0xffff0000 in (0x55330000,0x33310000),hex(id)
out={'kernel':os.uname().release,'unix_time':time.time(),'registers':{},'routers':[]}
for q in Path('/sys/bus/thunderbolt/devices').glob('*-1'):
 if '501f00000.nhi' in str(q.resolve()):
  out['routers'].append({k:(q/k).read_text().strip() for k in ['device_name','rx_lanes','tx_lanes','rx_speed','tx_speed','authorized'] if (q/k).exists()})
for offset in regs:
 guard();out['registers'][hex(offset)]=hex(read(base+offset))
cap=read(base)&255
assert 0x20<=cap<=0x100 and cap%4==0
guard();out['command']=hex(read(base+cap));out['status']=hex(read(base+cap+4))
guard();print(json.dumps(out,indent=2))
