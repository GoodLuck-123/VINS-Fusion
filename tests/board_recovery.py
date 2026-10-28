"""Board recovery and relocated runtime through one host script; no installation."""
import json,os,signal,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'runtime')]
from common import atomic,load
from cli import control,rpc,workspace
import yaml
config=yaml.safe_load((ROOT/'project.yaml').read_text());config['run']['name']='reconnect-check';config['dataset'].update(duration_s=30,ground_truth=None)
p=ROOT/'recovery-validation.yaml';p.write_text(yaml.safe_dump(config,sort_keys=False));c=load(p);c['_host']=False
with (ROOT/'build/reconnect-view.log').open('w') as log:
 viewer=subprocess.Popen([ROOT/'vins','-c',p,'run'],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 deadline=time.monotonic()+120
 while True:
  text=(ROOT/'build/reconnect-view.log').read_text()
  if '[replaying] reconnect-check/' in text:break
  assert viewer.poll() is None,text[-2000:];assert time.monotonic()<deadline;time.sleep(.2)
 before=control(c,'status');os.killpg(viewer.pid,signal.SIGINT);assert viewer.wait(timeout=15)==0
# No persistent SSH/viewer remains during this period.
time.sleep(6);after=control(c,'status');assert after['phase']=='replaying',after
assert after['observation']['image']['count']>before['observation']['image']['count']
subprocess.run([ROOT/'vins','-c',p,'stop'],check=True);subprocess.run([ROOT/'vins','-c',p,'stop'],check=True)
ended=control(c,'status');assert ended['phase']=='cancelled' and all(x==0 for x in ended['process_exits'].values()),ended
report={'disconnect':{'before':before,'after':after,'stopped':ended,'viewer_exit':0,'second_stop_exit':0}}
atomic(ROOT/'evidence/v0.1/board-disconnect.json',report)
code='''import json,os,shutil,subprocess,sys,time,hashlib
from pathlib import Path
ws=Path(sys.argv[1]);source=(ws/'current').resolve();dest=ws/'validation/relocated install';dest.parent.mkdir(exist_ok=True)
if dest.exists():shutil.rmtree(dest)
shutil.copytree(source,dest,copy_function=os.link)
env={'HOME':str(Path.home()),'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'}
check=subprocess.run([dest/'bin/vins','check'],env=env,capture_output=True,text=True);assert check.returncode==0,check.stderr
report={'clean_relocated_check_exit':check.returncode}
f=dest/'bin/vins_observer';data=f.read_bytes();f.unlink();f.write_bytes(data+b'corrupt');f.chmod(0o755)
bad=subprocess.run([dest/'bin/vins','check'],env=env,capture_output=True,text=True);assert bad.returncode and 'corrupt' in bad.stderr
report['corrupt_file']={'exit':bad.returncode,'error':bad.stderr.strip()};f.unlink();os.link(source/'bin/vins_observer',f)
active=json.loads((ws/'active.json').read_text());c=json.loads((Path(active['job'])/'project.json').read_text())
base=ws/'validation/relocated-task';base.mkdir(exist_ok=True);i=1
while (base/str(i).zfill(3)).exists():i+=1
job=base/str(i).zfill(3);job.mkdir();c.update(_workspace=str(base),_task='relocated/'+job.name);c['dataset']['duration_s']=15
(job/'project.json').write_text(json.dumps(c))
started=subprocess.run([dest/'bin/vins','start',job],env=env,capture_output=True,text=True);assert started.returncode==0,started.stderr
limit=time.monotonic()+90;maps=None
while True:
 s=json.loads((job/'state.json').read_text())
 if maps is None and s['phase']=='replaying' and s.get('observation',{}).get('image',{}).get('count',0)>5:
  maps=sorted(set(l.split()[-1] for l in Path('/proc/'+str(s['child_pids']['vins'])+'/maps').read_text().splitlines() if '/' in l))
 if s['phase'] in ['completed','failed','cancelled']:break
 assert time.monotonic()<limit,s;time.sleep(.3)
assert s['phase']=='completed' and (job/'files.json').is_file(),s
assert maps and any(str(dest) in x for x in maps),maps
report['relocated_replay']={'state':s,'maps':maps,'files':json.loads((job/'files.json').read_text())}
print(json.dumps(report))
'''
report['package']=rpc(c,code,[workspace(c)]);atomic(ROOT/'evidence/v0.1/board-recovery.json',report);print('BOARD RECOVERY AND RELOCATION PASSED',flush=True)
