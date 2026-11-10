#!/usr/bin/env python3
"""Audit migration from the working Ubuntu configuration without losing live drivers."""
import json,re,sys,subprocess
from pathlib import Path
old,new,source,output=map(Path,sys.argv[1:])
def parse(p):return dict(l.split('=',1) for l in p.read_text().splitlines() if l.startswith('CONFIG_') and '=' in l)
a,b=parse(old),parse(new)
changes={k:{'before':a.get(k),'after':b.get(k)} for k in sorted(a.keys()|b.keys()) if a.get(k)!=b.get(k)}
required=['64BIT','ARM64','ARM64_16K_PAGES','ARCH_APPLE','RUST','DRM_ASAHI','DRM_APPLE','DRM_APPLE_AUDIO','DRM_AMDGPU','USB4','USB4_APPLE_SOC','PCIE_APPLE','PCIE_APPLE_PCIEC','BLK_DEV_NVME','EXT4_FS','BTRFS_FS','DEVTMPFS','USB_XHCI_HCD','USB_STORAGE','USB_UAS','IOMMU_SUPPORT','APPLE_DART','PHY_APPLE_ATC','VIDEO_APPLE_AVD','BRANCH_PROFILE_NONE']
# Retain explicit runtime drivers and security controls, rather than require obsolete distro-only symbols.
required=[x for x in required if 'CONFIG_'+x in a or x in ['PCIE_APPLE_PCIEC']]
errors={k:changes.get(k,{'after':b.get(k)}) for x in required if (k:='CONFIG_'+x) and b.get(k) not in ('y','m')}
security=['SECURITY','SECURITY_APPARMOR','SECURITY_YAMA','SECCOMP','SECCOMP_FILTER','STRICT_KERNEL_RWX','STRICT_MODULE_RWX','MODULE_SIG','MODULE_SIG_ALL','RANDOMIZE_BASE','STACKPROTECTOR_STRONG','HARDENED_USERCOPY','FORTIFY_SOURCE']
for x in security:
 k='CONFIG_'+x
 if a.get(k)=='y' and b.get(k)!='y':errors[k]=changes.get(k)
# A still-declared previously enabled driver may not disappear silently during migration.
declared=set()
for n in subprocess.check_output(['git','-C',str(source),'ls-files','*Kconfig*'],text=True).splitlines():
 f=source/n
 if f.is_file():declared.update('CONFIG_'+m for m in re.findall(r'^\s*(?:menu)?config\s+(\w+)',f.read_text(errors='replace'),re.M))
removed={}
for k,v in changes.items():
 if a.get(k) in ('y','m') and b.get(k) not in ('y','m'):
  if k in declared:errors[k]=v
  else:removed[k]=v
report={'changes':changes,'obsolete_symbols_removed':removed,'unexpected_feature_losses':errors,'required_runtime_options':required,'result':'failed' if errors else 'passed'}
output.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'changes':len(changes),'obsolete_symbols':list(removed),'errors':errors},indent=2))
if errors:raise SystemExit('Configuration migration requires review')
