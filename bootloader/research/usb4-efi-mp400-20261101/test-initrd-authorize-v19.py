from pathlib import Path
import tempfile,subprocess,json
source=Path('authorize-mp400-v19.sh').read_text();cases=[]
for change in ['none','wrong-root','no-opt-in','wrong-vendor','wrong-device','wrong-id','wrong-port','already-authorized','already-attempted']:
 with tempfile.TemporaryDirectory(prefix='usb4-auth-test-') as tmp:
  t=Path(tmp);(t/'run').mkdir();(t/'proc').mkdir();(t/'sys/bus/thunderbolt/devices').mkdir(parents=True)
  port='381ac0000' if change=='wrong-port' else '501ac0000'
  real=t/f'sys/devices/platform/soc/{port}.cio/nhi/domain1/1-1';real.mkdir(parents=True)
  (t/'sys/bus/thunderbolt/devices/1-1').symlink_to(real)
  attrs={'vendor':'0xb8','device':'0x2463','unique_id':'01544c17-5069-cb4f-ffff-ffffffffffff','authorized':'0'}
  for tag,key in [('wrong-vendor','vendor'),('wrong-device','device'),('wrong-id','unique_id')]:
   if change==tag:attrs[key]='invalid'
  if change=='already-authorized':attrs['authorized']='1'
  for k,v in attrs.items():(real/k).write_text(v+'\n')
  cmd='root=UUID=1d4d5fd6-ea8a-4bb0-bf3c-2fc1f9e65935 usb4diag=v19'
  if change=='wrong-root':cmd=cmd.replace('root=UUID=1d4d5fd6','root=UUID=wrong')
  if change=='no-opt-in':cmd=cmd.replace('usb4diag=v19','')
  (t/'proc/cmdline').write_text(cmd+'\n')
  if change=='already-attempted':(t/'run/mp400-root-authorization-attempted').touch()
  script=source.replace('/sys/',tmp+'/sys/').replace('/proc/',tmp+'/proc/').replace('/run/',tmp+'/run/')
  script=script.replace('/bin/sh /usr/lib/usb4-capture-v19.sh before-authorization',':').replace('/bin/sh /usr/lib/usb4-capture-v19.sh after-authorization',':')
  p=t/'test.sh';p.write_text(script);r=subprocess.run(['sh',str(p)],capture_output=True,text=True);assert r.returncode==0,r.stderr
  expected='1' if change in ('none','already-authorized') else '0';assert (real/'authorized').read_text().strip()==expected,change
  cases.append(change)
result={'passed':True,'cases':cases};Path('initrd-authorize-v19-tests.json').write_text(json.dumps(result,indent=2)+'\n');print(result)
