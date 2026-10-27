import os, mmap, pathlib, subprocess, hashlib, time, json, argparse
from concurrent.futures import ThreadPoolExecutor
p=argparse.ArgumentParser();p.add_argument('--seconds',type=int,default=120);p.add_argument('--workers',type=int,default=1);a=p.parse_args()
dev=pathlib.Path('/sys/class/nvme/nvme1/device').resolve()
assert dev.name=='0001:03:00.0' and 'apple-apciec-step' in str(dev)
assert pathlib.Path('/sys/class/nvme/nvme1/model').read_text().strip()=='CT1000P310SSD8'
assert subprocess.check_output(['blockdev','--getro','/dev/nvme1n1']).strip()==b'1'
assert not any('/dev/nvme1n1' in x for x in pathlib.Path('/proc/mounts').read_text().splitlines())
size=int(pathlib.Path('/sys/class/block/nvme1n1/size').read_text())*512
boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
cpus=sorted(os.sched_getaffinity(0));start=time.monotonic();deadline=start+a.seconds
def worker(w):
    os.sched_setaffinity(0,{cpus[w%len(cpus)]})
    fd=os.open('/dev/nvme1n1',os.O_RDONLY|os.O_DIRECT)
    buf=mmap.mmap(-1,1048576);v=memoryview(buf);total=0;rounds=0
    try:
        while time.monotonic()<deadline:
            # Rotate through beginning, distributed middle regions and end.
            index=(rounds*a.workers+w)%65
            offset=((size-4*1048576)*index//64)//1048576*1048576
            hashes=[]
            for repeat in range(2):
                h=hashlib.sha256()
                for pos in range(offset,offset+4*1048576,1048576):
                    assert os.preadv(fd,[v],pos)==1048576
                    h.update(v);total+=1048576
                hashes.append(h.hexdigest())
            assert hashes[0]==hashes[1],(w,offset,hashes)
            assert pathlib.Path('/sys/class/nvme/nvme1/state').read_text().strip()=='live'
            rounds+=1
            print(json.dumps(dict(worker=w,cpu=cpus[w%len(cpus)],round=rounds,offset=offset,sha256=hashes[0],bytes=total)),flush=True)
            time.sleep(min(2,max(0,deadline-time.monotonic())))
        return dict(worker=w,bytes=total,rounds=rounds)
    finally:
        v.release();buf.close();os.close(fd)
with ThreadPoolExecutor(max_workers=a.workers) as pool:results=list(pool.map(worker,range(a.workers)))
assert pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()==boot
print(json.dumps(dict(result='PASS',elapsed=time.monotonic()-start,workers=results,boot_id=boot)),flush=True)
