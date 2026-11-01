#!/usr/bin/python3
import subprocess
from pathlib import Path
assert subprocess.check_output(['findmnt','-nro','UUID','/'],text=True).strip()=='1d4d5fd6-ea8a-4bb0-bf3c-2fc1f9e65935'
state=Path('/var/lib/usb4-mp400-diagnostic')
(state/'automatic-return.txt').write_text('Corrected return helper: completed external USB4 test; returning to default Ubuntu'+chr(10))
subprocess.run(['systemctl','disable','--now','usb4-mp400-return.timer'],check=True)
subprocess.run(['systemctl','reboot'],check=True)
