#!/usr/bin/env python3
"""Reject lost or altered pre-existing runtime features after olddefconfig."""
import json,sys
from pathlib import Path

def read(path):
 return dict(line.split('=',1) for line in Path(path).read_text().splitlines() if line.startswith('CONFIG_') and '=' in line)
a,b=map(read,sys.argv[1:3])
metadata={'CONFIG_CC_VERSION_TEXT','CONFIG_GCC_VERSION','CONFIG_AS_VERSION','CONFIG_LD_VERSION','CONFIG_RUSTC_VERSION','CONFIG_RUSTC_VERSION_TEXT','CONFIG_RUSTC_LLVM_VERSION','CONFIG_RUSTC_LLVM_MAJOR_VERSION','CONFIG_PAHOLE_VERSION','CONFIG_LOCALVERSION','CONFIG_VERSION_SIGNATURE','CONFIG_BUILD_SALT'}
changes={k:{'before':a.get(k),'after':b.get(k)} for k in sorted(a.keys()|b.keys()) if a.get(k)!=b.get(k)}
errors={k:v for k,v in changes.items() if k in a and k not in metadata}
report={'changes':changes,'unexpected_changes':errors,'baseline_enabled':sum(v in ('y','m') for v in a.values()),'result':'failed' if errors else 'passed'}
Path(sys.argv[3]).write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
if errors:sys.exit('Refusing a build with changed pre-existing configuration options')
for key in ['CONFIG_RUST','CONFIG_DRM_APPLE','CONFIG_DRM_APPLE_AUDIO','CONFIG_USB4_APPLE_SOC','CONFIG_PCIE_APPLE_PCIEC','CONFIG_BLK_DEV_NVME','CONFIG_DEBUG_INFO_BTF_MODULES']:
 if b.get(key) not in ('y','m'):sys.exit('Missing required option '+key)
