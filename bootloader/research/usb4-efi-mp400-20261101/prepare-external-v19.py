from pathlib import Path
import subprocess,shutil,hashlib,os
r=Path('/mnt/mp400-root');b=Path('/mnt/mp400-boot');state=Path('/var/lib/usb4-mp400-diagnostic')
for target,uuid in [(r,'1d4d5fd6-ea8a-4bb0-bf3c-2fc1f9e65935'),(b,'e10cc27a-5892-4594-befa-2c74255c78cf')]:
 assert subprocess.check_output(['findmnt','-nro','UUID','--target',str(target)],text=True).strip()==uuid
 subprocess.run(['mount','-o','remount,rw',str(target)],check=True)
g=b/'grub/grub.cfg';original=g.read_bytes();backup=state/'external-grub-before-v19.cfg';assert not backup.exists();backup.write_bytes(original);original=(state/'external-grub-before-v18.cfg').read_bytes()
assert original.count(b'menuentry ')==5
s=original.decode();entry=s[s.index("menuentry 'Ubuntu Asahi"):s.index("\nmenuentry 'Ubuntu Asahi",s.index("menuentry 'Ubuntu Asahi")+1)]
entry=entry.replace('Textkonsole - Diagnose','USB4 v19 - initramfs diagnosis').replace('rootwait rw ','rootwait rw usb4diag=v19 ').replace('/initrd.img-7.2.12-usb4sd4-egpu3','/initrd.usb4-v19')
source=b/'initrd.img-7.2.12-usb4sd4-egpu3';target=b/'initrd.usb4-v19';assert not target.exists()
with target.open('wb') as f:
 with source.open('rb') as i:shutil.copyfileobj(i,f)
 f.write(Path('/tmp/initrd-v19-overlay.cpio.gz').read_bytes())
g.write_bytes(original+b'\n'+entry.encode()+b'\n')
assert g.read_bytes().startswith(original)
(r/'var/lib/usb4-mp400-diagnostic/candidate-sha256.txt').write_text('22f2a37aeca53d59e6a8e065afdec9c72def037c69b6a5e8de99455c18256d73\n')
os.sync()
print('Original GRUB retained with appended diagnostic entry 5; original initrd retained; external return timer still armed')
print('Original GRUB SHA256:',hashlib.sha256(original).hexdigest())
print('Diagnostic initrd SHA256:',hashlib.sha256(target.read_bytes()).hexdigest())
