import os, mmap, pathlib, subprocess, hashlib, zlib, time, json
p = pathlib.Path('/sys/class/nvme/nvme1/device').resolve()
assert p.name == '0001:03:00.0' and 'apple-apciec-step' in str(p)
assert pathlib.Path('/sys/class/nvme/nvme1/model').read_text().strip() == 'CT1000P310SSD8'
assert subprocess.check_output(['blockdev','--getro','/dev/nvme1n1']).strip() == b'1'
assert not any('/dev/nvme1n1' in x for x in pathlib.Path('/proc/mounts').read_text().splitlines())
fd = os.open('/dev/nvme1n1', os.O_RDONLY | os.O_DIRECT)
buf = mmap.mmap(-1, 1024*1024)
view = memoryview(buf)
results=[]
for size, total in [(65536, 268435456), (1048576, 268435456)]:
    for repeat in range(2):
        h=hashlib.sha256(); crc=0xffffffff; start=time.monotonic()
        for offset in range(0,total,size):
            n=os.preadv(fd,[view[:size]],offset)
            assert n==size, (offset,n)
            h.update(view[:size]); crc=zlib.crc32(view[:size],crc)
        row=dict(chunk=size,total=total,repeat=repeat,seconds=time.monotonic()-start,
                 sha256=h.hexdigest(),kernel_crc32=f'{crc ^ 0xffffffff:08x}')
        results.append(row); print(json.dumps(row),flush=True)
assert len({r['sha256'] for r in results})==1
assert os.preadv(fd,[view[:4096]],0)==4096
assert bytes(view[512:520])==b'EFI PART'
sectors=int(pathlib.Path('/sys/class/block/nvme1n1/size').read_text())
assert os.preadv(fd,[view[:65536]],sectors*512-65536)==65536
assert bytes(view[65536-512:65536-504])==b'EFI PART'
print('PASS: repeated O_DIRECT reads, matching SHA256 and primary/backup GPT',flush=True)
view.release();buf.close();os.close(fd)
