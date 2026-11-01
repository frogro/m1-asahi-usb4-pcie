#!/usr/bin/env python3
"""Validate Android boot requirements without claiming runtime compatibility."""
import json,re,sys
from pathlib import Path
root=Path(__file__).resolve().parent
config=dict(re.findall(r'^(CONFIG_\w+)=(.*)$',Path(sys.argv[1]).read_text(),re.M))
required=json.loads((root/'required-features.json').read_text())
fail=[k for keys in required.values() for k in keys if config.get('CONFIG_'+k)!='y']
exact={'ARM64_16K_PAGES':'y','ANDROID_BINDER_DEVICES':'"binder,hwbinder,vndbinder"','LOCALVERSION':'"-googlebook-usb4-egpu1"','LSM':'"landlock,lockdown,yama,integrity,selinux,bpf"'}
fail += [k for k,v in exact.items() if config.get('CONFIG_'+k)!=v]
for k in ('USB4','USB4_APPLE_SOC','PCIE_APPLE_PCIEC','APPLE_DART','PHY_APPLE_ATC','DRM_ASAHI','DRM_APPLE','DRM_AMDGPU','VIDEO_APPLE_AVD','TYPEC_UCSI','UCSI_CCG','SND_HDA_INTEL','USB_XHCI_PCI','UDMABUF','VHOST_VSOCK'):
 if config.get('CONFIG_'+k) not in ('y','m'): fail.append(k)
result={'required_builtin_count':sum(map(len,required.values())),'missing':fail,'status':'FAIL' if fail else 'PASS','scope':'Static configuration; hardware validation pending'}
print(json.dumps(result,indent=2))
if fail:sys.exit(1)
