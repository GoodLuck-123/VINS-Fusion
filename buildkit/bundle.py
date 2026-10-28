"""Relocatable private VIO runtime; only OS glibc/loader remain external."""
import json,os,re,shutil,subprocess,tarfile,hashlib
from pathlib import Path
from fetch import ROOT,sha,obtain,CACHE
SYSTEM={'libc.so.6','libm.so.6','libpthread.so.0','libdl.so.2','librt.so.1','libresolv.so.2','libutil.so.1','libanl.so.1','libnss_files.so.2','libnss_dns.so.2','ld-linux-aarch64.so.1','ld-linux-x86-64.so.2'}

def copytree(src,dest):
    for p in src.rglob('*'):
        rel=p.relative_to(src)
        if not p.is_file() or any(x in {'include','cmake','pkgconfig','__pycache__','test','tests','doc','docs'} for x in rel.parts) or p.suffix in {'.a','.o','.pyc'}:continue
        q=dest/rel;q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
        if q.read_bytes()[:23].startswith(b'#!/usr/bin/python3\n'):q.write_bytes(q.read_bytes().replace(b'#!/usr/bin/python3\n',b'#!/usr/bin/env python3\n',1))

def needed(p):return re.findall(r'Shared library: \[(.*?)\]',subprocess.check_output(['readelf','-d',str(p)],text=True,stderr=subprocess.DEVNULL))
def elf(p):
    with p.open('rb') as f:return f.read(4)==b'\x7fELF'

def bundle(target):
    meta=json.loads((ROOT/'build'/target/'current.json').read_text());work=Path(meta['stage']).parent;sdk=Path(meta['sdk']);legacy=Path(meta['legacy']);native=target=='host';arch='x86_64' if native else 'aarch64'
    # A staging directory is replaced, never a previously accepted release.
    out=work/'package/install'
    if out.exists():shutil.rmtree(out)
    out.mkdir(parents=True);(out/'bin').mkdir();(out/'lib').mkdir()
    ros=sdk if native else sdk/'opt/ros/noetic'
    if native:
        for d in ['etc/ros','lib/rosout','lib/rosbag']:copytree(ros/d,out/'ros'/d)
        for d in (ros/'share').iterdir():
            if (d/'package.xml').is_file():copytree(d,out/'ros/share'/d.name)
        for p in (ros/'lib').glob('python*/site-packages'):
            for src in p.iterdir():
                if src.name.startswith(('numpy','cv2','cv_bridge','__pycache__')) or src.name.endswith(('.dist-info','.egg-info')):continue
                if src.is_dir():copytree(src,out/'python-extra'/src.name)
                elif src.is_file():
                    q=out/'python-extra'/src.name;q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,q)
        pyver=subprocess.check_output([sdk/'bin/python','-c','import sys;print("python%d.%d"%sys.version_info[:2])'],text=True).strip()
        # Python stdlib only; explicitly selected ROS/Python modules above.
        for p in (sdk/'lib'/pyver).iterdir():
            if p.name in {'site-packages','__pycache__'}:continue
            if p.is_dir():copytree(p,out/'python/lib'/pyver/p.name)
            elif p.is_file():q=out/'python/lib'/pyver/p.name;q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
        py=sdk/'bin/python'
        copytree(ros/'share/ros',out/'ros/share/ros')
    else:
        copytree(ros,out/'ros');copytree(sdk/'usr/lib/python3/dist-packages',out/'python-extra');copytree(sdk/'usr/lib/python3.8',out/'python/lib/python3.8');py=sdk/'usr/bin/python3.8'
    (out/'python/bin').mkdir(parents=True);shutil.copy2(py,out/'python/bin/python3')
    (out/'ros/bin').mkdir(parents=True,exist_ok=True)
    (out/'ros/.catkin').touch()
    for name in ['roscore','rosmaster','rosbag','rosparam','rostopic','rosnode','rosversion']:
        p=ros/'bin'/name
        if not p.is_file():p=sdk/'usr/bin'/name
        q=out/'ros/bin'/name;shutil.copy2(p,q)
        if not elf(q) and q.read_bytes().startswith(b'#!'):
            data=q.read_bytes().split(b'\n',1);q.write_bytes(b'#!/usr/bin/env python3\n'+data[1])
    # Pluginlib loads this by XML, so it is absent from ELF DT_NEEDED.
    (out/'ros/lib').mkdir(exist_ok=True)
    shutil.copy2(ros/'lib/librosbag_default_encryption_plugins.so',out/'ros/lib/librosbag_default_encryption_plugins.so')
    stage=Path(meta['stage'])
    shutil.copy2(stage/'lib/vins/vins_node',out/'bin/vins_node');shutil.copy2(work/'observer/vins_observer',out/'bin/vins_observer')
    copytree(ROOT/'runtime',out/'runtime')
    (out/'bin/vins').write_text('#!/usr/bin/env bash\nset -e\nroot=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)\nsource "$root/env.sh"\nexec python3 "$root/runtime/local.py" "$@"\n');(out/'bin/vins').chmod(0o755)
    (out/'env.sh').write_text('''#!/usr/bin/env bash
export VINS_INSTALL_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
unset PYTHONPATH PYTHONHOME ROS_PACKAGE_PATH AMENT_PREFIX_PATH CMAKE_PREFIX_PATH ROS_HOSTNAME VIRTUAL_ENV
export PYTHONNOUSERSITE=1 PYTHONHOME="$VINS_INSTALL_ROOT/python"
export PYTHONPATH="$VINS_INSTALL_ROOT/ros/lib/python3/dist-packages:$VINS_INSTALL_ROOT/python-extra"
export PATH="$VINS_INSTALL_ROOT/bin:$VINS_INSTALL_ROOT/python/bin:$VINS_INSTALL_ROOT/ros/bin:/usr/bin:/bin"
export LD_LIBRARY_PATH="$VINS_INSTALL_ROOT/lib:$VINS_INSTALL_ROOT/ros/lib"
export CMAKE_PREFIX_PATH="$VINS_INSTALL_ROOT/ros" ROS_PACKAGE_PATH="$VINS_INSTALL_ROOT/ros/share"
export ROS_ROOT="$VINS_INSTALL_ROOT/ros/share/ros" ROS_ETC_DIR="$VINS_INSTALL_ROOT/ros/etc/ros"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export ROS_DISTRO=noetic ROS_VERSION=1 ROS_PYTHON_VERSION=3 ROS_IP=127.0.0.1
''')
    dirs=[stage/'lib',legacy/'lib',ros/'lib',sdk/'lib']
    if not native:dirs += [sdk/'usr/lib/aarch64-linux-gnu',sdk/'lib/aarch64-linux-gnu',sdk/'usr/lib/aarch64-linux-gnu/blas',sdk/'usr/lib/aarch64-linux-gnu/lapack']
    pending=[]
    for p in out.rglob('*'):
        if p.is_file() and elf(p):pending.extend(needed(p))
    copied=set()
    while pending:
        name=pending.pop()
        if name in SYSTEM or name in copied:continue
        src=next((d/name for d in dirs if (d/name).is_file()),None)
        if src is None:raise RuntimeError('Missing private dependency: '+name)
        header=subprocess.check_output(['readelf','-h',str(src)],text=True)
        if ('Advanced Micro Devices X86-64' if native else 'AArch64') not in header:raise RuntimeError('Wrong ELF architecture: '+str(src))
        shutil.copy2(src,out/'lib'/name);copied.add(name);pending.extend(needed(src))
    # Remove build-machine RPATHs. Both direct and transitive libs resolve privately.
    patchelf=CACHE/'tools/patchelf/usr/bin/patchelf'
    if not patchelf.exists():
        archive=obtain(json.loads((ROOT/'buildkit/tool.lock.json').read_text()))
        subprocess.run(['dpkg-deb','-x',archive,CACHE/'tools/patchelf'],check=True)
    for p in out.rglob('*'):
        if p.is_file() and elf(p):subprocess.run([patchelf,'--remove-rpath',p],check=True)
    (out/'licenses').mkdir();shutil.copy2(ROOT/'LICENCE',out/'licenses/VINS-GPLv3')
    for name in ['opencv','ceres','eigen','vision_opencv']:
        for p in (ROOT/'third_party'/name).glob('*'):
            if p.is_file() and p.name.upper().startswith(('LICENSE','COPYING')):shutil.copy2(p,out/'licenses'/(name+'-'+p.name))
    release=dict(version='0.1.0',architecture=arch,build=meta,platform_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),system_libraries=sorted(SYSTEM))
    (out/'release.json').write_text(json.dumps(release,indent=2)+'\n')
    manifest={str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file()}
    (out/'files.json').write_text(json.dumps(manifest,indent=2)+'\n')
    ident=hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest()[:16]
    dest=ROOT/'releases/v0.1.0'/('host' if native else 'rk3588')/ident
    dest.mkdir(parents=True,exist_ok=True)
    final=dest/'install'
    if not final.exists():shutil.copytree(out,final)
    archive=dest/('vins-'+arch+'-0.1.0.tar.gz')
    with tarfile.open(archive,'w:gz') as t:t.add(final,arcname='install')
    record=dict(id=ident,install=str(final),archive=str(archive),sha256=sha(archive),architecture=arch,files=len(manifest))
    (dest/'package.json').write_text(json.dumps(record,indent=2)+'\n');(dest/'SHA256SUMS').write_text(record['sha256']+'  '+archive.name+'\n')
    (ROOT/'releases'/('host.json' if native else 'board.json')).write_text(json.dumps(record,indent=2)+'\n')
    shutil.rmtree(out)
    print(json.dumps(record),flush=True);return record
if __name__=='__main__':
    import sys
    bundle(sys.argv[1])
