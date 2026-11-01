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
subprocess.run(['mount','-o','rw,nosuid,nodev','/dev/disk/by-uuid/44FD-1525',str(p)],check=True)
try:
 target=p/'m1n1/boot.bin';assert sha(target)=='7dd9bc657620925bf4aa796efb91ac29c570cf4cbf1ddab612ef6dfe9cf5cc47'
 shutil.copyfile(candidate,target.with_suffix('.new'));os.sync();assert sha(target.with_suffix('.new'))==expected;os.replace(target.with_suffix('.new'),target);os.sync()
finally:subprocess.run(['umount',str(p)],check=True)
subprocess.run(['systemctl','enable','usb4-mp400-restore.service'],check=True)
subprocess.run(['asahi-bless','--next','--set-boot','Asahi Linux','--yes'],check=True)
print('Diagnostic installed, one-shot selected, automatic restoration armed:',expected,flush=True)
subprocess.run(['systemctl','reboot'],check=True)
