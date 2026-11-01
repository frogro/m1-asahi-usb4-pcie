from pathlib import Path
import hashlib,subprocess,os,shutil,sys
candidate=Path(sys.argv[1]);expected=sys.argv[2]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert os.geteuid()==0 and sha(candidate)==expected
assert subprocess.check_output(['findmnt','-nro','UUID','/'],text=True).strip()=='e4d52d5a-56e9-4320-90f4-4223563b08d6'
assert sha(Path('/boot/efi/m1n1/boot.bin'))=='8ba8fc1d6eea83f2626860784d36a8ac5afc052110352b4ba64afdd3ce57fe60'
p=Path('/mnt/asahi-usb4-test');state=Path('/var/lib/usb4-mp400-diagnostic')
assert sha(state/'boot-integrated.bin')=='7dd9bc657620925bf4aa796efb91ac29c570cf4cbf1ddab612ef6dfe9cf5cc47'
(state/'candidate-sha256.txt').write_text(expected+'\n')
(state/'restore.py').write_text('''#!/usr/bin/python3
from pathlib import Path
import subprocess,hashlib,shutil,os
state=Path('/var/lib/usb4-mp400-diagnostic');p=Path('/mnt/asahi-usb4-restore');p.mkdir(exist_ok=True)
subprocess.run(['mount','-o','rw,nosuid,nodev','/dev/disk/by-uuid/44FD-1525',str(p)],check=True)
try:
 t=p/'m1n1/boot.bin'; h=hashlib.sha256(t.read_bytes()).hexdigest()
 if h== (state/'candidate-sha256.txt').read_text().strip():
  b=state/'boot-integrated.bin'
  assert hashlib.sha256(b.read_bytes()).hexdigest()=='7dd9bc657620925bf4aa796efb91ac29c570cf4cbf1ddab612ef6dfe9cf5cc47'
  shutil.copyfile(b,t.with_suffix('.restore'));os.sync();os.replace(t.with_suffix('.restore'),t);os.sync()
  print('Integrated U-Boot restored')
 for name in ['usb4-logonly.txt','usb4-logonly-shutdown-v7.txt','usb4-mp400-enter.log','usb4-mp400-link.log','usb4-mp400-link-v8.log','usb4-mp400-link-v9.log','usb4-mp400-link-v10.log','usb4-mp400-link-v11.log','usb4-mp400-link-v12.log','usb4-mp400-link-v13.log','usb4-mp400-link-v14.log','usb4-mp400-link-v15.log']:
  if (p/name).exists():shutil.copy2(p/name,state/name)
finally:subprocess.run(['umount',str(p)],check=True)
for prop,name in [('u-boot,usb4-diagnostic-log','ram-transcript.txt'),('u-boot,integration','ram-integration.txt')]:
 src=Path('/sys/firmware/devicetree/base/chosen')/prop
 if src.exists():
  (state/name).write_bytes(src.read_bytes())
  (state/'ram-boot-id.txt').write_text(Path('/proc/sys/kernel/random/boot_id').read_text())
subprocess.run(['systemctl','disable','usb4-mp400-restore.service'],check=True)
''')
# External root gets the same bootloader recovery, plus a single bounded return.
r=Path('/mnt/mp400-root')
assert subprocess.check_output(['findmnt','-nro','UUID','--target',str(r)],text=True).strip()=='1d4d5fd6-ea8a-4bb0-bf3c-2fc1f9e65935'
subprocess.run(['mount','-o','remount,rw',str(r)],check=True)
es=r/'var/lib/usb4-mp400-diagnostic';es.mkdir(parents=True,exist_ok=True)
assert not (es/'v16-prepared').exists()
for name in ['boot-integrated.bin','candidate-sha256.txt','restore.py']:
 assert not (es/name).exists(), name
 shutil.copy2(state/name,es/name)
unitdir=r/'etc/systemd/system'
restore_unit=Path('/etc/systemd/system/usb4-mp400-restore.service').read_text()
return_script="""#!/usr/bin/python3
import subprocess
from pathlib import Path
assert subprocess.check_output(['findmnt','-nro','UUID','/'],text=True).strip()=='1d4d5fd6-ea8a-4bb0-bf3c-2fc1f9e65935'
state=Path('/var/lib/usb4-mp400-diagnostic')
(state/'automatic-return.txt').write_text('Bounded external USB4 EFI boot test completed; returning to default Ubuntu'+chr(10))
subprocess.run(['systemctl','disable','usb4-mp400-return.timer'],check=True)
subprocess.run(['systemctl','reboot'],check=True)
"""
compile(return_script,'external-return.py','exec')
(es/'return.py').write_text(return_script)
units={
 'usb4-mp400-restore.service':restore_unit,
 'usb4-mp400-return.service':'[Unit]\nDescription=Return from bounded USB4 EFI test\n[Service]\nType=oneshot\nExecStart=/usr/bin/python3 /var/lib/usb4-mp400-diagnostic/return.py\n',
 'usb4-mp400-return.timer':'[Unit]\nDescription=Five-minute return for USB4 EFI test\n[Timer]\nOnBootSec=300s\nAccuracySec=1s\nUnit=usb4-mp400-return.service\n[Install]\nWantedBy=timers.target\n'}
for name,content in units.items():
 assert not (unitdir/name).exists(), name
 (unitdir/name).write_text(content)
for group,name in [('multi-user.target.wants','usb4-mp400-restore.service'),('timers.target.wants','usb4-mp400-return.timer')]:
 d=unitdir/group;d.mkdir(exist_ok=True)
 (d/name).symlink_to('../'+name)
(es/'v16-prepared').write_text(expected+'\n')
os.sync()
for mount in ['/mnt/mp400-efi','/mnt/mp400-boot','/mnt/mp400-root']:
 subprocess.run(['umount',mount],check=True)
subprocess.run(['mount','-o','rw,nosuid,nodev','/dev/disk/by-uuid/44FD-1525',str(p)],check=True)
try:
 target=p/'m1n1/boot.bin';assert sha(target)=='7dd9bc657620925bf4aa796efb91ac29c570cf4cbf1ddab612ef6dfe9cf5cc47'
 shutil.copyfile(candidate,target.with_suffix('.new'));os.sync();assert sha(target.with_suffix('.new'))==expected;os.replace(target.with_suffix('.new'),target);os.sync()
 subprocess.run(['grub-editenv',str(p/'EFI/Asahi/grubenv'),'set','next_entry=0'],check=True)
finally:subprocess.run(['umount',str(p)],check=True)
subprocess.run(['systemctl','enable','usb4-mp400-restore.service'],check=True)
subprocess.run(['asahi-bless','--next','--set-boot','Asahi Linux','--yes'],check=True)
print('Diagnostic installed, one-shot selected, automatic restoration armed:',expected,flush=True)
subprocess.run(['systemctl','reboot'],check=True)
