#!/usr/bin/env python3
import argparse,json,re,hashlib
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('linux',type=Path);p.add_argument('uart',type=Path);a=p.parse_args()
l=json.loads(a.linux.read_text());s=a.uart.read_text();phases={}
for phase,off,val in re.findall(r'DWC3-SNAPSHOT ([^ ]+) reg\[(0x[0-9a-f]+)\]=(0x[0-9a-f]+|0)',s):
 if off in phases.setdefault(phase,{}):raise SystemExit('Duplicate snapshot')
 phases[phase][off]=val
assert set(phases)=={'before-remove','before-acio','after-acio'},'Incomplete capture'
for phase,regs in phases.items():assert set(regs)==set(l['registers']),phase
out={'linux_sha256':hashlib.sha256(a.linux.read_bytes()).hexdigest(),'uart_sha256':hashlib.sha256(a.uart.read_bytes()).hexdigest(),'snapshots':phases,'differences':{}}
for phase,regs in phases.items():
 out['differences'][phase]={off:{'linux':val,'uboot':regs[off],'xor':hex(int(val,16)^int(regs[off],16))} for off,val in l['registers'].items() if int(val,16)!=int(regs[off],16)}
print(json.dumps(out,indent=2))
