"""Small real-process failure checks using the installed package, without rebuilding."""
import json,os,signal,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'runtime'))
from common import atomic,load

install=Path(json.loads((ROOT/'releases/host.json').read_text())['install']);base=ROOT/'build/lifecycle-validation';base.mkdir(exist_ok=True);i=1
while (base/str(i).zfill(3)).exists():i+=1
base=base/str(i).zfill(3);base.mkdir()
terminal={'completed','failed','cancelled'}
def get(job):
    p=job/'state.json';return json.loads(p.read_text()) if p.exists() else {}
def wait(job,test,timeout=40):
    limit=time.monotonic()+timeout
    while time.monotonic()<limit:
        s=get(job)
        if test(s):return s
        time.sleep(.2)
    raise AssertionError('timeout waiting for '+str(job)+': '+str(s))
def start(name,change=lambda c:None):
    job=base/name;job.mkdir();c=load(ROOT/'project.yaml');c['dataset']['duration_s']=30;c['_workspace']=str(base);c['_task']=name;change(c);atomic(job/'project.json',c)
    subprocess.run([install/'bin/vins','start',job],check=True,capture_output=True,text=True);return job

def finish(job,phase,explanation=None):
    s=wait(job,lambda s:s.get('phase') in terminal)
    assert s['phase']==phase,s
    if explanation:assert explanation in s.get('error',''),s
    for name,pid in s.get('child_pids',{}).items():assert not Path('/proc/'+str(pid)).exists(),(name,pid)
    assert (job/'files.json').is_file()
    return s
report={}
for name in ['vins','observer']:
    job=start('kill-'+name);s=wait(job,lambda s:s.get('phase')=='replaying' and s.get('observation',{}).get('image',{}).get('count',0)>10)
    if name=='vins':
        # A competing launch must be rejected while the first task owns the lock.
        other=base/'duplicate';other.mkdir();atomic(other/'project.json',json.loads((job/'project.json').read_text()))
        r=subprocess.run([install/'bin/vins','start',other],capture_output=True,text=True);assert r.returncode and 'Active task' in r.stderr;rpt={'exit':r.returncode,'error':r.stderr.strip()};report['duplicate']=rpt
    os.kill(s['child_pids'][name],signal.SIGKILL);report['kill-'+name]=finish(job,'failed',name+' exited')
job=start('timeout',lambda c:c['run'].update(timeout_s=6));report['timeout']=finish(job,'failed','Run timeout');assert report['timeout']['exit_code']==124
job=start('stop');wait(job,lambda s:s.get('phase')=='replaying');(job/'stop.request').touch();report['stop']=finish(job,'cancelled','Requested stop');assert all(v==0 for v in report['stop']['process_exits'].values())
atomic(base/'report.json',report);print('LIFECYCLE CHECKS PASSED')
