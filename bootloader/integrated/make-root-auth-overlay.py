#!/usr/bin/env python3
"""Generate a dracut hook for one explicitly selected external root enclosure.

No device access, installation, kernel change or automatic authorization here.
The output gzip/newc archive can be appended to the original Linux initramfs.
"""
import argparse,gzip,hashlib,json,re,stat,uuid
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for name in ['root-uuid','router-uuid','vendor','device','controller','output']:p.add_argument('--'+name,required=True)
a=p.parse_args();root=str(uuid.UUID(a.root_uuid));router=str(uuid.UUID(a.router_uuid))
for key in ['vendor','device']:
 if not re.fullmatch(r'0x[0-9a-f]{1,4}',getattr(a,key)):p.error(key+' must be a lowercase hex identifier')
if not re.fullmatch(r'[0-9a-f]{8,12}\.cio',a.controller):p.error('controller must be the selected SoC controller name')
o=Path(a.output);o.mkdir(parents=True,exist_ok=False)
marker='external-root-auth-'+hashlib.sha256((root+router+a.controller).encode()).hexdigest()[:16]
hook=f'''#!/bin/sh
# Generated for a selected external root; other attached devices are untouched.
authorize_selected_external_root() {{
 case " $(cat /proc/cmdline) " in *' root=UUID={root} '*) ;; *) return 0;; esac
 for d in /sys/bus/thunderbolt/devices/*; do
  [ -f "$d/authorized" ] || continue
  [ "$(cat "$d/vendor" 2>/dev/null)" = {a.vendor} ] || continue
  [ "$(cat "$d/device" 2>/dev/null)" = {a.device} ] || continue
  [ "$(cat "$d/unique_id" 2>/dev/null)" = {router} ] || continue
  case "$(readlink -f "$d")" in /sys/devices/platform/soc/{a.controller}/*) ;; *) continue;; esac
  [ "$(cat "$d/authorized")" = 0 ] || continue
  [ -e /run/{marker} ] && continue
  : > /run/{marker}
  if printf '1\\n' > "$d/authorized"; then
   echo 'External root: selected enclosure authorized.'
  else
   echo 'External root: selected enclosure authorization failed.' >&2
  fi
 done
 return 0
}}
authorize_selected_external_root
'''
(o/'authorize-selected-root.sh').write_text(hook)
files={'usr/lib/dracut/hooks/initqueue/settled/11-authorize-selected-root.sh':hook}
archive=bytearray();ino=1
dirs=sorted({str(parent) for name in files for parent in Path(name).parents if str(parent)!='.'},key=lambda n:(n.count('/'),n))
for name,data in [(d,None) for d in dirs]+list(files.items())+[('TRAILER!!!','')]:
 b=(data or '').encode();n=name.encode()+b'\0';mode=(stat.S_IFDIR if data is None else stat.S_IFREG)|0o755
 fields=[ino,mode,0,0,1,0,len(b),0,0,0,0,len(n),0]
 archive.extend(b'070701'+''.join(f'{v:08x}' for v in fields).encode()+n)
 archive.extend(b'\0'*((-len(archive))%4));archive.extend(b);archive.extend(b'\0'*((-len(archive))%4));ino+=1
blob=gzip.compress(bytes(archive),mtime=0);(o/'root-auth.cpio.gz').write_bytes(blob)
meta={'root_uuid':root,'router_uuid':router,'vendor':a.vendor,'device':a.device,'controller':a.controller,'marker':marker,'sha256':hashlib.sha256(blob).hexdigest(),'installed':False,'no_diagnostic_capture':True}
(o/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n');print(json.dumps(meta))
