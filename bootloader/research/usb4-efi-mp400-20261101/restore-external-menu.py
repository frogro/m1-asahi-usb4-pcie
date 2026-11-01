from pathlib import Path
import hashlib,os,shutil,subprocess
assert subprocess.check_output(['findmnt','-nro','UUID','/'],text=True).strip()=='1d4d5fd6-ea8a-4bb0-bf3c-2fc1f9e65935'
s=Path('/tmp/grub.cfg');assert hashlib.sha256(s.read_bytes()).hexdigest()=='48c3b49e3c36d9a31bfd6f10228acbe81310cf3c09f4b493e8356ad4a9d59d17'
t=Path('/boot/grub/grub.cfg');assert 'USB4 v19' in t.read_text()
shutil.copy2(t,Path('/var/lib/usb4-mp400-diagnostic/grub-v19-tested.cfg'))
shutil.copyfile(s,t.with_suffix('.restore'));os.sync();os.replace(t.with_suffix('.restore'),t);os.sync()
r=Path('/var/lib/usb4-mp400-diagnostic/return.py');shutil.copy2(r,r.with_name('return-original-broken.py'))
s=Path('/tmp/return-v19.py');compile(s.read_text(),str(s),'exec');shutil.copyfile(s,r)
print('Original five-entry GRUB restored and corrected return helper syntax verified',flush=True)
subprocess.run(['systemctl','reset-failed','usb4-mp400-return.service'],check=True)
subprocess.run(['systemctl','start','--no-block','usb4-mp400-return.service'],check=True)
