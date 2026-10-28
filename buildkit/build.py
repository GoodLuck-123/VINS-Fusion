"""Pinned native/cross VIO builds. No board compilation or system package installs."""
import argparse, hashlib, json, os, shutil, subprocess, sys
from pathlib import Path
from fetch import ROOT,CACHE,packages,sources,obtain,sha

def call(args,**kw):
    print('+ '+' '.join(map(str,args)),flush=True)
    subprocess.run(list(map(str,args)),check=True,**kw)

def fingerprint():
    paths=[ROOT/'buildkit'/n for n in ['build.py','sources.lock.json','aarch64.cmake','native_cmake_overrides.cmake','opencv4_legacy_compat.h','locks/ros1-sdk.json','locks/toolchain.json','locks/host-linux-64.txt']]
    for d in ['runtime/observer','camera_models','vins_estimator','third_party']:
        paths += [p for p in (ROOT/d).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    return hashlib.sha256(json.dumps({str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)},sort_keys=True).encode()).hexdigest()[:16]

def host_bootstrap():
    meta=json.loads((ROOT/'buildkit/host-tool.json').read_text()); tool=CACHE/'tools/micromamba'
    if not tool.exists():
        import tarfile
        archive=obtain(meta);tool.parent.mkdir(parents=True,exist_ok=True)
        with tarfile.open(archive) as t:tool.write_bytes(t.extractfile('bin/micromamba').read())
        tool.chmod(0o755)
    if sha(tool)!=meta['binary_sha256']:raise RuntimeError('Invalid micromamba binary')
    prefix=CACHE/'host-env';lock=ROOT/'buildkit/locks/host-linux-64.txt'; marker=prefix/'.vins-lock'
    if not marker.exists() or marker.read_text()!=sha(lock):
        call([tool,'create','-y','--no-rc','-r',CACHE/'mamba','-p',prefix,'--file',lock])
        marker.write_text(sha(lock))
    return tool,prefix

def main(target,jobs,inside=False):
    CACHE.mkdir(exist_ok=True);native=target=='host'
    os.environ.update(MAMBA_ROOT_PREFIX=str(CACHE/'mamba'),CONDA_PKGS_DIRS=str(CACHE/'mamba/pkgs'),XDG_CACHE_HOME=str(CACHE/'xdg'),CCACHE_DIR=str(CACHE/'ccache'),CCACHE_TEMPDIR=str(CACHE/'ccache-tmp'))
    sources()
    if native and not inside:
        tool,prefix=host_bootstrap()
        call([tool,'run','-p',prefix,'/usr/bin/python3',__file__,'--target','host','--jobs',jobs,'--inside']);return
    sdk=CACHE/('host-env' if native else 'sysroot');tool=CACHE/'toolchain'
    if not native:
        packages('toolchain',tool);packages('ros1-sdk',sdk)
    ident=fingerprint()
    current=ROOT/'build'/target/'current.json'
    if current.exists():
        prior=json.loads(current.read_text())
        if prior['source_fingerprint']==ident and (Path(prior['stage'])/'lib/vins/vins_node').is_file():
            print('BUILD REUSED '+prior['stage'],flush=True);return
    work=ROOT/'build'/target/ident; stage=work/'stage';legacy=work/'libraries'
    work.mkdir(parents=True,exist_ok=True);stage.mkdir(exist_ok=True);legacy.mkdir(exist_ok=True)
    env=os.environ.copy()
    if not native:
        hostlibs=CACHE/'compiler-libs';hostlibs.mkdir(exist_ok=True)
        for pat in ['libisl.so.22','libgmp.so.10','libmpc.so.3','libmpfr.so.6','libbfd*-arm64.so*','libopcodes*-arm64.so*','libctf*-arm64.so*']:
            for p in (tool/'usr/lib/x86_64-linux-gnu').glob(pat):
                dest=hostlibs/p.name
                if not dest.exists():dest.symlink_to(p)
        env.update(VINS_ARM_SYSROOT=str(sdk),VINS_CROSS_ROOT=str(tool),VINS_ARM_PREFIX=str(legacy),VINS_ARM_ROS_PREFIX=str(stage),LD_LIBRARY_PATH=str(hostlibs),PYTHONPATH=str(sdk/'opt/ros/noetic/lib/python3/dist-packages')+':'+str(sdk/'usr/lib/python3/dist-packages'),PKG_CONFIG_SYSROOT_DIR=str(sdk),PKG_CONFIG_LIBDIR=str(sdk/'usr/lib/aarch64-linux-gnu/pkgconfig'))
        env.pop('CONDA_PREFIX',None)
    ros=sdk if native else sdk/'opt/ros/noetic'
    common=['-DCMAKE_BUILD_TYPE=Release','-DCMAKE_INSTALL_LIBDIR=lib','-DCMAKE_POLICY_VERSION_MINIMUM=3.5','-DCATKIN_ENABLE_TESTING=OFF','-DCMAKE_EXPORT_COMPILE_COMMANDS=ON']
    if not native:common+=['-DCMAKE_TOOLCHAIN_FILE='+str(ROOT/'buildkit/aarch64.cmake')]
    def build(name,source,flags=(),install=False,targets=()):
        dest=work/name
        call(['cmake','-S',source,'-B',dest,*common,*flags],env=env)
        call(['cmake','--build',dest,'-j',jobs,*(['--target',*targets] if targets else [])],env=env)
        if install:call(['cmake','--install',dest],env=env)
    libflags=['-DCMAKE_INSTALL_PREFIX='+str(legacy)]
    build('eigen',ROOT/'third_party/eigen',libflags+['-DBUILD_TESTING=OFF','-DEIGEN_BUILD_DOC=OFF'],True)
    cvflags=['-DBUILD_LIST=core,imgproc,imgcodecs,calib3d,features2d,flann,video,highgui']
    cvflags+=['-D'+x+'=OFF' for x in ['ENABLE_CCACHE','WITH_ADE','BUILD_opencv_gapi','BUILD_TESTS','BUILD_PERF_TESTS','BUILD_EXAMPLES','BUILD_opencv_python2','BUILD_opencv_python3','WITH_QT','WITH_GTK','WITH_FFMPEG','WITH_GSTREAMER','WITH_V4L','WITH_OPENCL','WITH_IPP','WITH_ITT','WITH_EIGEN','WITH_TIFF','WITH_OPENEXR','WITH_WEBP','WITH_JASPER','WITH_PROTOBUF','BUILD_JAVA']]
    build('opencv',ROOT/'third_party/opencv',libflags+cvflags,True)
    sparse=['-DCMAKE_PREFIX_PATH='+str(legacy)+';'+str(sdk if native else sdk/'usr'),'-DEigen3_DIR='+str(legacy/'share/eigen3/cmake'),'-DEIGEN_INCLUDE_DIR='+str(legacy/'include/eigen3'),'-DCMAKE_DISABLE_FIND_PACKAGE_TBB=TRUE','-DBLA_VENDOR=Generic','-DSUITESPARSE=ON','-DLAPACK=ON','-DBUILD_SHARED_LIBS=ON','-DBUILD_TESTING=OFF','-DBUILD_EXAMPLES=OFF','-DBUILD_BENCHMARKS=OFF','-DCXX11=ON']
    if not native:sparse+=['-DCMAKE_LIBRARY_PATH='+str(sdk/'usr/lib/aarch64-linux-gnu/blas')+';'+str(sdk/'usr/lib/aarch64-linux-gnu/lapack')]
    build('ceres',ROOT/'third_party/ceres',libflags+sparse,True)
    bridge=work/'bridge-source'
    if not bridge.exists():
        shutil.copytree(ROOT/'third_party/vision_opencv/cv_bridge',bridge)
        for f in ['CMakeLists.txt','src/CMakeLists.txt']:
            p=bridge/f;s=p.read_text().replace('if(NOT ANDROID)','if(NOT ANDROID AND VINS_CV_BRIDGE_PYTHON)').replace('catkin_python_setup()','if(VINS_CV_BRIDGE_PYTHON)\ncatkin_python_setup()\nendif()');p.write_text(s)
    flags=['-DCATKIN_DEVEL_PREFIX='+str(stage),'-DCMAKE_INSTALL_PREFIX='+str(stage),'-DCMAKE_PREFIX_PATH='+str(stage)+';'+str(legacy)+';'+str(ros)+';'+str(sdk/'usr'),'-DPYTHON_EXECUTABLE='+str(sdk/'bin/python' if native else '/usr/bin/python3'),'-DOpenCV_DIR='+str(legacy/'lib/cmake/opencv4'),'-DCeres_DIR='+str(legacy/'lib/cmake/Ceres'),'-DEigen3_DIR='+str(legacy/'share/eigen3/cmake'),'-DEIGEN3_INCLUDE_DIR='+str(legacy/'include/eigen3'),'-DCMAKE_PROJECT_INCLUDE='+str(ROOT/'buildkit/native_cmake_overrides.cmake'),'-DVINS_CV_BRIDGE_PYTHON=OFF']
    build('bridge',bridge,flags)
    build('camera_models',ROOT/'camera_models',flags,targets=['camera_models'])
    build('vins',ROOT/'vins_estimator',flags,targets=['vins_node'])
    build('observer',ROOT/'runtime/observer',flags)
    meta=dict(id=ident,target=target,stage=str(stage),legacy=str(legacy),sdk=str(sdk),source_fingerprint=fingerprint())
    (work/'build.json').write_text(json.dumps(meta,indent=2)+'\n')
    (ROOT/'build'/target/'current.json').write_text(json.dumps(meta,indent=2)+'\n')
    print('BUILD COMPLETE '+str(work),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--target',choices=['host','board'],required=True);p.add_argument('--jobs',type=int,default=4);p.add_argument('--inside',action='store_true');a=p.parse_args();main(a.target,a.jobs,a.inside)
