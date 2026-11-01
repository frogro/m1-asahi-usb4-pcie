from pathlib import Path
import gzip,stat,json
w=Path(__file__).resolve().parent
capture=r'''#!/bin/sh
case " $(cat /proc/cmdline) " in *' usb4diag=v18 '*) ;; *) exit 0;; esac
phase="$1"
[ -e "/run/usb4-capture-$phase" ] && exit 0
: > "/run/usb4-capture-$phase"
mountdir=/run/usb4-diag-esp
mkdir -p "$mountdir"
modprobe vfat 2>/dev/null || :
if mount -t vfat -o rw,nosuid,nodev /dev/disk/by-uuid/44FD-1525 "$mountdir"; then
 out="$mountdir/usb4-v18-$phase.txt"
 {
  echo "USB4 initramfs diagnostic v18 phase=$phase"
  uname -a
  cat /proc/cmdline
  cat /proc/uptime
  cat /proc/partitions
  ls -l /dev/disk/by-uuid
  for d in /sys/bus/thunderbolt/devices/*; do
   echo "ROUTER $d"
   for a in device_name vendor_name vendor device unique_id authorized security rx_speed tx_speed generation; do
    if [ -f "$d/$a" ]; then printf '%s=' "$a"; cat "$d/$a"; fi
   done
  done
  dmesg
  cat /sys/firmware/devicetree/base/chosen/u-boot,usb4-diagnostic-log 2>/dev/null || :
 } > "$out" 2>&1
 sync
 umount "$mountdir"
fi
exit 0
'''
files={'usr/lib/usb4-capture-v18.sh':capture}
for phase in ['initqueue/timeout','shutdown-emergency','pre-pivot']:
 tag=phase.replace('/','-')
 files['usr/lib/dracut/hooks/'+phase+'/98-usb4-capture.sh']='#!/bin/sh\n/bin/sh /usr/lib/usb4-capture-v18.sh '+tag+'\n'
archive=bytearray(); ino=1
dirs=sorted({str(parent) for name in files for parent in Path(name).parents if str(parent)!='.'}, key=lambda n:(n.count('/'),n))
for name,data in [(d,None) for d in dirs]+list(files.items())+[('TRAILER!!!','')]:
 b=(data or '').encode();n=name.encode()+b'\0'; mode=(stat.S_IFDIR if data is None else stat.S_IFREG)|0o755
 fields=[ino,mode,0,0,1,0,len(b),0,0,0,0,len(n),0]
 archive.extend(b'070701'+''.join(f'{v:08x}' for v in fields).encode()+n)
 archive.extend(b'\0'*((-len(archive))%4));archive.extend(b);archive.extend(b'\0'*((-len(archive))%4));ino+=1
(w/'initrd-v18-overlay.cpio.gz').write_bytes(gzip.compress(bytes(archive),mtime=0))
(w/'initrd-v18-capture.sh').write_text(capture)
(w/'initrd-v18-files.json').write_text(json.dumps(files,indent=2)+'\n')
