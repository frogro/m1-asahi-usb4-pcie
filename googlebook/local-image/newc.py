"""Metadata-preserving newc reader/writer from local image tooling; no extraction."""
import stat
from pathlib import Path
def read_newc(data):
    records=[]; pos=0
    while pos<len(data):
        while pos<len(data) and data[pos]==0: pos+=1
        if pos==len(data): break
        magic=data[pos:pos+6]
        if magic not in (b'070701',b'070702'): raise ValueError('Invalid newc header')
        fields=[int(data[pos+6+i*8:pos+14+i*8],16) for i in range(13)]
        size,ns=fields[6],fields[11]
        if ns<1 or pos+110+ns>len(data): raise ValueError('Invalid name bounds')
        raw=data[pos+110:pos+110+ns]
        if raw[-1:]!=b'\0': raise ValueError('Unterminated name')
        name=raw[:-1].decode(); start=(pos+110+ns+3)&~3
        if start+size>len(data): raise ValueError('Invalid data bounds')
        body=data[start:start+size]; pos=(start+size+3)&~3
        if magic==b'070702' and sum(body)&0xffffffff!=fields[12]: raise ValueError('CPIO CRC mismatch')
        if name=='TRAILER!!!': continue
        if name.startswith('/') or '..' in Path(name).parts: raise ValueError('Unsafe archive path')
        records.append((name,fields,body))
    return records


def write_newc(records):
    result=bytearray()
    for name,fields,body in records+[('TRAILER!!!',[0,stat.S_IFREG,0,0,1,0,0,0,0,0,0,0,0],b'')]:
        f=fields.copy(); raw=name.encode()+b'\0'; f[6]=len(body); f[11]=len(raw); f[12]=0
        result+=b'070701'+b''.join(f'{v:08x}'.encode() for v in f)+raw
        result+=bytes(-len(result)%4); result+=body; result+=bytes(-len(result)%4)
    return bytes(result)
