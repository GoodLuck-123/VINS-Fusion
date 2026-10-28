"""Run via SSH stdin during capture; no board writes or dependency installation."""
import json,os,platform
from pathlib import Path
ws=Path.home()/'vins-workspace';job=Path(json.loads((ws/'active.json').read_text())['job']);s=json.loads((job/'state.json').read_text())
assert s['phase']=='capturing',s['phase']
bad=[];install=s['install'];out=dict(task=s['task'],install=install,platform=list(platform.uname()),processes={})
allowed=('libc.','libc-','libm.','libm-','libpthread.','libpthread-','libdl.','libdl-','librt.','librt-','libresolv.','libresolv-','libutil.','libutil-','libnss_files','libnss_dns','ld-','ld-linux','libanl.','libanl-')
for name,pid in s['child_pids'].items():
    root=Path('/proc')/str(pid);maps=sorted(set(line.split(None,5)[5].strip() for line in (root/'maps').read_text().splitlines() if '/' in line))
    for path in maps:
        if '.so' in path and not path.startswith(install+'/'):
            if not Path(path).name.startswith(allowed):bad.append((name,path))
        
        if path.startswith(('/opt/ros','/opt/spinnaker','/home/firefly/driver_ws')):bad.append((name,path))
    env=dict(x.split('=',1) for x in (root/'environ').read_bytes().decode().split('\0') if '=' in x)
    out['processes'][name]=dict(pid=pid,maps=maps,env={k:env.get(k) for k in ['LD_LIBRARY_PATH','PYTHONHOME','PYTHONPATH','FLIR_GENTL64_CTI','GENICAM_GENTL64_PATH','ROS_MASTER_URI']})
camera=out['processes']['camera']['maps'];assert any('FLIR_GenTL.cti' in x for x in camera);assert any('/lib/libusb-1.0.so' in x for x in camera)
out['unexpected_external_libraries']=bad
print(json.dumps(out,indent=2))
assert not bad,bad
