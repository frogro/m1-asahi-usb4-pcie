#!/usr/bin/env python3
from pathlib import Path
import sys,struct,json,hashlib,gzip
sys.path.insert(0,'/usr/lib/python3/dist-packages');import libfdt
import argparse
p=argparse.ArgumentParser(description='Build an opt-in M1 display DT from a verified common-menu DT; never installs')
p.add_argument('input',type=Path);p.add_argument('output',type=Path);p.add_argument('--sha256',required=True)
a=p.parse_args()
raw=a.input.read_bytes()
if hashlib.sha256(raw).hexdigest()!=a.sha256:raise SystemExit('Input DT hash mismatch')
if a.output.exists():raise SystemExit('Output exists')
f=libfdt.Fdt(raw);f.resize(len(raw)+65536)
def snap():
 out={}
 def walk(n,path):
  props={};p=f.first_property_offset(n,quiet=(libfdt.NOTFOUND,))
  while p>=0:
   v=f.get_property_by_offset(p);props[v.name]=bytes(v).hex();p=f.next_property_offset(p,quiet=(libfdt.NOTFOUND,))
  out[path]=props;c=f.first_subnode(n,quiet=(libfdt.NOTFOUND,))
  while c>=0:walk(c,path.rstrip('/')+'/'+f.get_name(c));c=f.next_subnode(c,quiet=(libfdt.NOTFOUND,))
 walk(0,'/');return out
before=snap();nextph=max(int(p['phandle'],16) for p in before.values() if 'phandle' in p)+1
pack=lambda *v:struct.pack('>'+'I'*len(v),*v)
def put(path,name,data):f.setprop(f.path_offset(path),name,data)
def get(path,name):return f.getprop(f.path_offset(path),name)
def ph(path):
 global nextph
 try:return struct.unpack('>I',get(path,'phandle'))[0]
 except libfdt.FdtException as e:
  assert e.err==-libfdt.NOTFOUND
  n=nextph;nextph+=1;put(path,'phandle',pack(n));return n
def alias(name):return get('/aliases',name).as_str()
dcp=alias('dcpext');phy=[alias('atcphy'+str(i)) for i in range(2)];cio=[alias('usb4-'+str(i)+'-acio') for i in range(2)]
mux=['/soc/mux@38304c000','/soc/mux@50304c000'];pd=['/soc/i2c@235010000/usb-pd@38','/soc/i2c@235010000/usb-pd@3f']
assert b'apple,t8103\0' in bytes(get('/','compatible'))
put(dcp,'apple,auto-dp-routing',b'')
put(dcp,'apple,native-dp-ports',pack(*(ph(p) for p in pd)))
put(dcp,'apple,dpin-ports',pack(*(ph(p) for p in cio)))
put(dcp,'phys',pack(ph(phy[0]),6,ph(phy[1]),6));put(dcp,'phy-names',b'dp0-phy\0dp1-phy\0')
put(dcp,'mux-controls',pack(ph(mux[0]),0,ph(mux[1]),0));put(dcp,'mux-control-names',b'dp0-xbar\0dp1-xbar\0')
for i in range(2):
 put(cio[i],'codex,atcphy',pack(ph(phy[i])));put(cio[i],'codex,dpin-callback-test',b'')
 put(cio[i],'mux-controls',pack(ph(mux[i]),1));put(cio[i],'mux-control-names',b'dp-xbar\0')
 put(phy[i],'codex,dpin-clock-test',b'');put(mux[i],'codex,dpin-staged-test',b'')
put('/chosen','u-boot,integration',b'20261105-auto-dp-routing-rfc1\0')
# Keep one legacy Googlebook provider. The additional provider is Ubuntu opt-in.
f.delprop(f.path_offset(cio[0]),'codex,dpin-callback-test')
put(cio[0],'apple,auto-dpin-provider',b'')
f.pack();after=snap()
allowed={dcp,*pd,*phy,*cio,*mux,'/chosen'}
assert {n for n in before if before[n]!=after[n]}<=allowed
assert after[dcp]['codex,dpin-provider']==before[dcp]['codex,dpin-provider']
for name in ['usb4_0_pcie','usb4_1_pcie']:assert before[alias(name)]==after[alias(name)]
assert after['/soc/dcp@231c00000']==before['/soc/dcp@231c00000']
assert before['/config']==after['/config']
with a.output.open('xb') as out:out.write(bytes(f.as_bytearray()))
print(hashlib.sha256(a.output.read_bytes()).hexdigest())
