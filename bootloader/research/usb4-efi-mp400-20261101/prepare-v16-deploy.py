from pathlib import Path
s=Path('deploy-diagnostic.py').read_text()
needle="subprocess.run(['mount','-o','rw,nosuid,nodev','/dev/disk/by-uuid/44FD-1525',str(p)],check=True)\ntry:\n target="
assert s.count(needle)==1
prep='''# External root gets the same bootloader recovery, plus a single bounded return.
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
 'usb4-mp400-return.service':'[Unit]\\nDescription=Return from bounded USB4 EFI test\\n[Service]\\nType=oneshot\\nExecStart=/usr/bin/python3 /var/lib/usb4-mp400-diagnostic/return.py\\n',
 'usb4-mp400-return.timer':'[Unit]\\nDescription=Five-minute return for USB4 EFI test\\n[Timer]\\nOnBootSec=300s\\nAccuracySec=1s\\nUnit=usb4-mp400-return.service\\n[Install]\\nWantedBy=timers.target\\n'}
for name,content in units.items():
 assert not (unitdir/name).exists(), name
 (unitdir/name).write_text(content)
for group,name in [('multi-user.target.wants','usb4-mp400-restore.service'),('timers.target.wants','usb4-mp400-return.timer')]:
 d=unitdir/group;d.mkdir(exist_ok=True)
 (d/name).symlink_to('../'+name)
(es/'v16-prepared').write_text(expected+'\\n')
os.sync()
for mount in ['/mnt/mp400-efi','/mnt/mp400-boot','/mnt/mp400-root']:
 subprocess.run(['umount',mount],check=True)
'''
s=s.replace(needle,prep+needle)
s=s.replace("finally:subprocess.run(['umount',str(p)],check=True)\nsubprocess.run(['systemctl','enable'", " subprocess.run(['grub-editenv',str(p/'EFI/Asahi/grubenv'),'set','next_entry=0'],check=True)\nfinally:subprocess.run(['umount',str(p)],check=True)\nsubprocess.run(['systemctl','enable'")
Path('deploy-v16.py').write_text(s)
compile(s,'deploy-v16.py','exec')
print('Deployment script syntax checked; external UUID guarded; automatic return 300s; original Ubuntu untouched')
