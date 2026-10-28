"""Build small target adapters against the verified VIO stage and private SDK."""
import hashlib,json,os,subprocess
from pathlib import Path
from fetch import ROOT,CACHE,sha

def prepare():
    lock=ROOT/'buildkit/spinnaker.lock.json';meta=json.loads(lock.read_text());dest=ROOT/'third_party/spinnaker';marker=dest/'.vins-sdk'
    archives=[]
    for item in meta['packages']:
        p=CACHE/'archives'/item['file']
        if not p.is_file():raise ValueError('Missing vendor SDK: '+str(p)+'; obtain Spinnaker '+meta['version']+' ARM64 from '+meta['vendor_url']+' (see docs/05_HARDWARE_V02.md)')
        if sha(p)!=item['sha256']:raise ValueError('Vendor SDK SHA256 mismatch: '+str(p))
        archives.append(p)
    if not marker.exists() or marker.read_text().strip()!=sha(lock):
        dest.mkdir(parents=True,exist_ok=True)
        for p in archives:subprocess.run(['dpkg-deb','-x',str(p),str(dest)],check=True)
        marker.write_text(sha(lock)+'\n')
    return dest/'opt/spinnaker'

def build(jobs=4):
    sdk=prepare();base=json.loads((ROOT/'build/board/current.json').read_text());stage=Path(base['stage']);legacy=Path(base['legacy']);sysroot=Path(base['sdk'])
    files=[ROOT/'buildkit/hardware.py',ROOT/'buildkit/spinnaker.lock.json']+[p for p in (ROOT/'third_party/drivers').rglob('*') if p.is_file()]
    ident=hashlib.sha256(json.dumps(dict(base=base['source_fingerprint'],files={str(p.relative_to(ROOT)):sha(p) for p in sorted(files)}),sort_keys=True).encode()).hexdigest()[:16]
    work=ROOT/'build/hardware'/ident;record=ROOT/'build/hardware/current.json'
    env=os.environ.copy();env.update(VINS_ARM_SYSROOT=str(sysroot),VINS_CROSS_ROOT=str(CACHE/'toolchain'),VINS_ARM_PREFIX=str(legacy),VINS_ARM_ROS_PREFIX=str(stage),LD_LIBRARY_PATH=str(CACHE/'compiler-libs'),PYTHONPATH=str(sysroot/'opt/ros/noetic/lib/python3/dist-packages')+':'+str(sysroot/'usr/lib/python3/dist-packages'))
    flags=['-DCMAKE_TOOLCHAIN_FILE='+str(ROOT/'buildkit/aarch64.cmake'),'-DCMAKE_BUILD_TYPE=Release','-DCMAKE_POLICY_VERSION_MINIMUM=3.5','-DCATKIN_ENABLE_TESTING=OFF','-DPYTHON_EXECUTABLE=/usr/bin/python3','-DCMAKE_PREFIX_PATH='+str(stage)+';'+str(legacy)+';'+str(sysroot/'opt/ros/noetic')+';'+str(sysroot/'usr'),'-DOpenCV_DIR='+str(legacy/'lib/cmake/opencv4'),'-DSPINNAKER_ROOT='+str(sdk)]
    subprocess.run(['cmake','-S',str(ROOT/'third_party/drivers'),'-B',str(work),*flags],env=env,check=True)
    subprocess.run(['cmake','--build',str(work),'-j',str(jobs)],env=env,check=True)
    record.parent.mkdir(parents=True,exist_ok=True);record.write_text(json.dumps(dict(id=ident,stage=str(work),sdk=str(sdk),core_fingerprint=base['source_fingerprint'],sdk_lock_sha256=sha(ROOT/'buildkit/spinnaker.lock.json')),indent=2)+'\n')
    return json.loads(record.read_text())
if __name__=='__main__':build()
