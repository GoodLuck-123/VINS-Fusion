#!/usr/bin/env bash
set -euo pipefail
export LD_LIBRARY_PATH="$VINS_REMOTE_PAYLOAD/lib"
logs="$VINS_REMOTE_ROOT/logs"
python3 - <<'PY'
import hashlib,json,os,pathlib
root=pathlib.Path(os.environ['VINS_REMOTE_PAYLOAD'])
for relative,expected in json.loads((root/'files.json').read_text()).items():
    assert hashlib.sha256((root/relative).read_bytes()).hexdigest()==expected, relative
PY
ldd "$VINS_REMOTE_PAYLOAD/shared_probe" > "$logs/ldd.txt"
! grep -q 'not found' "$logs/ldd.txt"
"$VINS_REMOTE_PAYLOAD/shared_probe" memfd > "$logs/memfd.log" 2>&1
grep -q 'PASS memfd:' "$logs/memfd.log"
# Do not silently switch heaps/backends or change global device permissions.
device=${VINS_DMA_HEAP_DEVICE:-/dev/dma_heap/system}
stat "$device" > "$logs/heap_device.txt"
"$VINS_REMOTE_PAYLOAD/shared_probe" dma_heap "$device" > "$logs/dma_heap.log" 2>&1
grep -q 'PASS dma_heap:' "$logs/dma_heap.log"
python3 - <<'PY'
import json,os,pathlib,re
logs=pathlib.Path(os.environ['VINS_REMOTE_ROOT'])/'logs'
result={}
for backend,number in [('memfd',1),('dma_heap',2)]:
    text=(logs/(backend+'.log')).read_text()
    writer=re.search(r'shared_writer backend='+backend+r' frames=(\d+).*outstanding=(\d+) failed=(\d+) sha0=(\w+) sha1=(\w+)',text)
    reader=re.search(r'shared_reader backend='+str(number)+r' frames=(\d+) verified=(\d+) failed=(\d+) sha0=(\w+) sha1=(\w+)',text)
    assert writer and reader, text
    assert writer.groups()[:3]==('1000','0','0'), writer.groups()
    assert reader.groups()[:3]==('1000','1000','0'), reader.groups()
    assert writer.groups()[3:]==reader.groups()[3:], 'Pixel/header digests differ'
    result[backend]=dict(frames=1000,verified=1000,outstanding=0,failed=0,sha0=writer[4],sha1=writer[5])
(logs/'validation.json').write_text(json.dumps(result,indent=2)+'\n')
PY
