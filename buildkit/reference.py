"""Validation-only pristine VINS node, sharing exactly the tested dependency build."""
import argparse,json,os,shutil,subprocess
from pathlib import Path
from fetch import ROOT,CACHE

def main(target,inside=False):
    native=target=='host';meta=json.loads((ROOT/'build'/target/'current.json').read_text());work=Path(meta['stage']).parent;sdk=Path(meta['sdk']);stage=Path(meta['stage']);legacy=Path(meta['legacy'])
    if native and not inside:
        subprocess.run([CACHE/'tools/micromamba','run','-r',CACHE/'mamba','-p',sdk,'/usr/bin/python3',__file__,'--target','host','--inside'],check=True,env={**os.environ,'MAMBA_ROOT_PREFIX':str(CACHE/'mamba'),'XDG_CACHE_HOME':str(CACHE/'xdg')});return
    source=work/'reference-source';out=work/'reference-stage'
    if not source.exists():shutil.copytree(ROOT/'vins_estimator',source)
    for f in ['src/rosNodeTest.cpp','src/estimator/estimator.cpp']:
        (source/f).write_bytes(subprocess.check_output(['git','-C',ROOT,'show','be55a93:vins_estimator/'+f]))
    env=os.environ.copy()
    if not native:env.update(VINS_ARM_SYSROOT=str(sdk),VINS_CROSS_ROOT=str(CACHE/'toolchain'),VINS_ARM_PREFIX=str(legacy),VINS_ARM_ROS_PREFIX=str(stage),LD_LIBRARY_PATH=str(CACHE/'compiler-libs'),PYTHONPATH=str(sdk/'opt/ros/noetic/lib/python3/dist-packages')+':'+str(sdk/'usr/lib/python3/dist-packages'))
    flags=['-DCMAKE_BUILD_TYPE=Release','-DCATKIN_ENABLE_TESTING=OFF','-DCATKIN_DEVEL_PREFIX='+str(out),'-DCMAKE_INSTALL_PREFIX='+str(out),'-DPYTHON_EXECUTABLE='+str(sdk/'bin/python' if native else '/usr/bin/python3'),'-DCMAKE_PREFIX_PATH='+str(stage)+';'+str(legacy)+';'+str(sdk if native else sdk/'opt/ros/noetic')+';'+str(sdk/'usr'),'-DOpenCV_DIR='+str(legacy/'lib/cmake/opencv4'),'-DCeres_DIR='+str(legacy/'lib/cmake/Ceres'),'-DEigen3_DIR='+str(legacy/'share/eigen3/cmake'),'-DEIGEN3_INCLUDE_DIR='+str(legacy/'include/eigen3'),'-DCMAKE_PROJECT_INCLUDE='+str(ROOT/'buildkit/native_cmake_overrides.cmake')]
    if not native:flags+=['-DCMAKE_TOOLCHAIN_FILE='+str(ROOT/'buildkit/aarch64.cmake')]
    subprocess.run(['cmake','-S',source,'-B',work/'reference-build',*flags],env=env,check=True)
    subprocess.run(['cmake','--build',work/'reference-build','-j','4','--target','vins_node'],env=env,check=True)
    (work/'reference.json').write_text(json.dumps({'base':'be55a937a57436548ddfb1bd324bc1e9a9e828e0','stage':str(out),'target':target,'dependencies_build':meta},indent=2)+'\n')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--target',required=True,choices=['host','board']);p.add_argument('--inside',action='store_true');a=p.parse_args();main(a.target,a.inside)
