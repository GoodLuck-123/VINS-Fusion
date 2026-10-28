"""Package-local controls; used over SSH and after source install/env.sh."""
import argparse,fcntl,json,os,subprocess,sys,time
from pathlib import Path
from common import atomic,load,verify_install
TERMINAL={'completed','failed','cancelled'}

def state(workspace):
    active=workspace/'active.json'
    if not active.exists():return {'phase':'idle'}
    job=Path(json.loads(active.read_text())['job']);p=job/'state.json'
    result=json.loads(p.read_text()) if p.exists() else {'phase':'starting','task':str(job)}
    if result['phase'] not in TERMINAL:
        pid=result.get('pid',json.loads(active.read_text()).get('pid'))
        try:cmd=Path('/proc/%s/cmdline'%pid).read_bytes()
        except OSError:cmd=b''
        if str(job).encode() not in cmd:
            result.update(phase='failed',exit_code=1,error='supervisor_exit: task owner is no longer alive');atomic(p,result)
    return result

def start(job,install):
    job=Path(job);c=json.loads((job/'project.json').read_text());workspace=Path(c['_workspace']);workspace.mkdir(parents=True,exist_ok=True)
    with (workspace/'.start.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        old=state(workspace)
        if old['phase'] not in TERMINAL|{'idle'}:raise RuntimeError('Active task exists: '+old.get('task','unknown'))
        if (job/'state.json').exists():raise RuntimeError('Task already started; use status/pull')
        f=(job/'agent.log').open('w');p=subprocess.Popen([sys.executable,str(install/'runtime/agent.py'),str(job),str(install)],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True);f.close()
        atomic(workspace/'active.json',dict(job=str(job),pid=p.pid))
        deadline=time.monotonic()+5
        while not (job/'state.json').exists():
            if p.poll() is not None:raise RuntimeError('Supervisor failed; see '+str(job/'agent.log'))
            if time.monotonic()>deadline:raise RuntimeError('Supervisor readiness timed out')
            time.sleep(.1)
    return state(workspace)

def main():
    p=argparse.ArgumentParser();p.add_argument('-c','--config',default='project.yaml');p.add_argument('--workspace',default=str(Path.home()/'vins-workspace'));p.add_argument('command',choices=['start','status','stop','check','run']);p.add_argument('job',nargs='?');a=p.parse_args()
    root=Path(os.environ['VINS_INSTALL_ROOT']);workspace=Path(a.workspace).expanduser().resolve()
    if a.command=='check':result=verify_install(root)
    elif a.command=='start':result=start(Path(a.job),root)
    elif a.command=='status':result=state(workspace)
    elif a.command=='stop':
        active=json.loads((workspace/'active.json').read_text());(Path(active['job'])/'stop.request').touch();result=state(workspace)
    else:
        c=load(a.config);workspace.mkdir(parents=True,exist_ok=True);name=c['run']['name'];base=workspace/'experiments'/name;base.mkdir(parents=True,exist_ok=True)
        i=1
        while (base/str(i).zfill(3)).exists():i+=1
        job=base/str(i).zfill(3);job.mkdir();c.update(_workspace=str(workspace),_task=name+'/'+job.name);atomic(job/'project.json',c);result=start(job,root)
    print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':
    try:main()
    except Exception as e:print(str(e),file=sys.stderr);sys.exit(1)
