"""Capture only owned process mappings and explicit environment; no system changes."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'runtime')]
from common import load,atomic
from cli import control,rpc
c=load(ROOT/'project.yaml');c['_host']=sys.argv[1]=='host';s=control(c,'status');assert s['phase']=='replaying',s
code='''import json,sys,os,platform
from pathlib import Path
s=json.loads(sys.argv[1]);out={'uname':list(platform.uname()),'processes':{}}
for name,pid in s['child_pids'].items():
 root=Path('/proc/'+str(pid));maps=sorted(set(l.split()[-1] for l in (root/'maps').read_text().splitlines() if '/' in l))
 env=dict(v.split('=',1) for v in (root/'environ').read_bytes().decode().split('\\0') if '=' in v)
 out['processes'][name]={'pid':pid,'maps':maps,'env':{k:env.get(k) for k in ['PATH','PYTHONPATH','PYTHONHOME','LD_LIBRARY_PATH','ROS_MASTER_URI','ROS_PACKAGE_PATH','OPENBLAS_NUM_THREADS','OMP_NUM_THREADS']}}
try:out['temperature_millic']=Path('/sys/class/thermal/thermal_zone0/temp').read_text().strip()
except OSError:out['temperature_millic']=None
out['cpufreq']={str(p):p.read_text().strip() for p in Path('/sys/devices/system/cpu').glob('cpufreq/policy*/scaling_governor')}
print(json.dumps(out))
'''
out=rpc(c,code,[json.dumps(s)]);install=s['install'];bad=[]
for name,row in out['processes'].items():
 for p in row['maps']:
  if not p.startswith(install+'/') and ('.so' in p or p.startswith('/opt/')):
   if not Path(p).name.startswith(('libc.','libc-','libm.','libm-','libpthread.','libpthread-','libdl.','libdl-','librt.','librt-','libresolv.','libresolv-','libutil.','libutil-','libnss_files','libnss_dns','ld-','ld-linux','libanl.','libanl-')):bad.append((name,p))
assert not bad,bad
atomic(ROOT/'evidence/v0.1'/('runtime-maps-'+sys.argv[1]+'.json'),out);print('PRIVATE RUNTIME MAPS VERIFIED',sys.argv[1])
