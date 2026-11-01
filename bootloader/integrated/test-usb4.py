#!/usr/bin/env python3
"""Replay actual USB4 C functions and exclusive boot dispatch. No hardware access."""
from pathlib import Path
import sys,shutil,subprocess,json
src=Path(sys.argv[1]).resolve();out=Path(sys.argv[2]).resolve();out.mkdir(parents=True,exist_ok=False)
fixtures=Path(__file__).resolve().parent/'tests/usb4'
for p in fixtures.iterdir():
 if p.is_file():shutil.copy2(p,out/p.name)
(out/'source').symlink_to(src,target_is_directory=True)
results={}
for name in ['test-router-v10.py','test-router-write-v10.py','test-preflight-v13.py','test-query-v12.py','test-credit-guard-v12.py','test-paths-v15.py','test-endpoint-v15.py','test-boot-policy.py']:
 p=subprocess.run([sys.executable,str(out/name)],cwd=out,capture_output=True,text=True)
 (out/(name+'.log')).write_text(p.stdout+p.stderr)
 results[name]={'returncode':p.returncode,'output':p.stdout[-500:]}
 if p.returncode:
  (out/'result.json').write_text(json.dumps(results,indent=2)+'\n');raise SystemExit(name+' failed; see '+str(out/(name+'.log')))
(out/'result.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(results))
