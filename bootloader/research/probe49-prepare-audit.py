from pathlib import Path
import subprocess,json,hashlib,struct,shutil,gzip,datetime
r=Path(__file__).parent;root=Path('/home/frank/usb4-test-work/uboot-hardware-test-20261031');old=root/'probe48-pciec-reference';out=root/'probe49-tunable-audit'
linux=r.parent/'linux-saved-reference/live-egpu2.dtb'
groups=[('phy-common-a','/soc/phy@503000000','apple,tunable-common-a'),('phy-axi2af','/soc/phy@503000000','apple,tunable-axi2af'),('phy-common-b','/soc/phy@503000000','apple,tunable-common-b'),('phy-lane0-cio','/soc/phy@503000000','apple,tunable-lane0-cio'),('phy-lane1-cio','/soc/phy@503000000','apple,tunable-lane1-cio'),('acio-rc','/soc/cio@501ac0000','apple,tunable-rc'),('nhi','/soc/cio@501ac0000/nhi@f00000','apple,tunable-nhi')]
refs=[];cmds=['setenv probe_audit PASS']
for label,node,prop in groups:
 vals=[int(v,16) for v in subprocess.check_output(['fdtget','-t','x',str(linux),node,prop],text=True).split()];assert len(vals)%3==0
 data=b''.join(struct.pack('>I',v) for v in vals);sha=hashlib.sha256(data).hexdigest()
 refs.append(dict(label=label,node=node,property=prop,bytes=len(data),triples=len(vals)//3,sha256=sha,cells=vals))
 cmds.append(f'echo TUNABLE-AUDIT BEGIN {label}; if fdt get addr probe_addr {node} {prop}; then if fdt get size probe_size {node} {prop}; then echo TUNABLE-AUDIT SIZE {label} ${{probe_size}}; if hash sha256 ${{probe_addr}} ${{probe_size}} probe_sum; then echo TUNABLE-AUDIT SHA256 {label} ${{probe_sum}}; if test "${{probe_sum}}" = "{sha}"; then echo TUNABLE-AUDIT MATCH {label}; else setenv probe_audit FAIL; echo TUNABLE-AUDIT MISMATCH {label}; fdt print {node} {prop}; fi; else setenv probe_audit FAIL; echo TUNABLE-AUDIT HASH-ERROR {label}; fi; else setenv probe_audit FAIL; echo TUNABLE-AUDIT SIZE-ERROR {label}; fi; else setenv probe_audit FAIL; echo TUNABLE-AUDIT MISSING {label}; fi; echo TUNABLE-AUDIT END {label}')
cmds.append('echo TUNABLE-AUDIT RESULT ${probe_audit}')
audit='; '.join(cmds);(r/'audit-command.txt').write_text(audit+'\n');(r/'reference.json').write_text(json.dumps({'source':str(linux),'source_sha256':hashlib.sha256(linux.read_bytes()).hexdigest(),'groups':refs},indent=2)+'\n')
# Exercise actual FDT get/hash/print commands in sandbox before a hardware run.
b=Path('/tmp/asahi-universal-boot-20261031/phy-candidate/sandbox');tests=[]
for name,mut in [('reference',None),('missing',0),('modified',1),('duplicated',2)]:
 dt=r/(name+'.dtb');shutil.copy2(linux,dt)
 if mut is not None:
  g=refs[0]
  if mut==0:args=['fdtput','-d',str(dt),g['node'],g['property']]
  else:
   vals=list(g['cells'])
   if mut==1:vals[2]^=1
   if mut==2:vals=vals+vals
   args=['fdtput','-t','x',str(dt),g['node'],g['property'],*[hex(v) for v in vals]]
  subprocess.run(args,check=True)
 script=f'host load hostfs - 1000000 {dt}; fdt addr 1000000; '+audit
 p=subprocess.run([str(b/'u-boot'),'-T','-c',script],cwd=b,capture_output=True,text=True,timeout=30);(r/(name+'.log')).write_text(p.stdout+p.stderr)
 want='PASS' if mut is None else 'FAIL';assert 'TUNABLE-AUDIT RESULT '+want in p.stdout,(name,p.stdout[-2000:]);assert p.stdout.count('TUNABLE-AUDIT MATCH ')==(7 if mut is None else 6)
 if mut==0:assert 'TUNABLE-AUDIT MISSING phy-common-a' in p.stdout
 if mut in [1,2]:assert 'TUNABLE-AUDIT MISMATCH phy-common-a' in p.stdout and 'apple,tunable-common-a' in p.stdout
 tests.append({'case':name,'expected':want,'passed':True})
(r/'command-tests.json').write_text(json.dumps(tests,indent=2)+'\n')
# Freeze a RAM-only audit: no ATC/ACIO/NHI initialization command at all.
out.mkdir()
for n in ['m1n1-release.bin','j274-probe-hv.dtb','run-hv-once.py','uboot.config','u-boot-nodtb.bin']:shutil.copy2(old/n,out/n)
for n in ['m1n1-client','venv']:(out/n).symlink_to((old/n).resolve())
oldcmd=(old/'bootcommand.txt').read_text().strip()
before=oldcmd[oldcmd.index('setenv probe_internal FAIL'):oldcmd.index('; if test "${probe_internal}" = "PASS"; then echo CD321X')]
after=oldcmd[oldcmd.rindex('setenv probe_internal FAIL'):oldcmd.index('; echo CD321X-POWER-AFTER-BEGIN')]
cmd='echo UBOOT-PROBE49 TUNABLE-HANDOFF-AUDIT; '+before+'; if test "${probe_internal}" = "PASS"; then if fdt addr ${fdtcontroladdr}; then '+audit+'; else echo TUNABLE-AUDIT FDT-ERROR; fi; fi; '+after+'; echo NO-PHY-OR-ACIO-INITIALIZATION; echo EXTERNAL-DISK-NOT-ACCESSED; echo NO-EXTERNAL-PCIE-TUNNEL; echo RESET-IN-10-SECONDS; sleep 10; reset'
assert 'atcm1' not in cmd and 'usb4pciec' not in cmd
(out/'bootcommand.txt').write_text(cmd+'\n');subprocess.run(['fdtput','-t','s',str(out/'j274-probe-hv.dtb'),'/config','bootcmd',cmd],check=True)
(out/'m1n1-uboot-probe-hv.bin').write_bytes((out/'m1n1-release.bin').read_bytes()+(out/'j274-probe-hv.dtb').read_bytes()+gzip.compress((out/'u-boot-nodtb.bin').read_bytes(),mtime=0))
files=['m1n1-release.bin','j274-probe-hv.dtb','u-boot-nodtb.bin','uboot.config','bootcommand.txt','m1n1-uboot-probe-hv.bin','run-hv-once.py'];manifest={n:hashlib.sha256((out/n).read_bytes()).hexdigest() for n in files};(out/'hv-artifacts.json').write_text(json.dumps(manifest,indent=2)+'\n')
x={'probe':49,'base_probe':48,'purpose':'Compare all seven used PHY, ACIO and NHI tunable lists as handed to U-Boot against saved working Linux DT','groups':7,'reference_triples':sum(g['triples'] for g in refs),'command_tests_passed':4,'uboot_binary_unchanged':True,'new_source_changes':False,'phy_initialization':False,'acio_initialization':False,'nhi_rings':False,'ram_only':True,'external_disk_io':False,'external_pcie_tunnel':False,'bootcommand_bytes':len(cmd),'hardware_pending':True,'payload_directory':str(out),'artifact_sha256':manifest}
(r/'preparation.json').write_text(json.dumps(x,indent=2)+'\n');(out/'README.txt').write_text(x['purpose']+'\nNo PHY/ACIO initialization. No external disk access. Mandatory reset unchanged.\n')
print(json.dumps({k:v for k,v in x.items() if k!='artifact_sha256'},indent=2))
