"""One serial fixed 30s pair; reports observations, not statistical performance proof."""
import json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'runtime'))
from common import atomic,load
install=Path(json.loads((ROOT/'releases/host.json').read_text())['install']);base=ROOT/'build/monitor-overhead';base.mkdir(exist_ok=True);i=1
while (base/str(i).zfill(3)).exists():i+=1
base=base/str(i).zfill(3);base.mkdir();report={}
for enabled in [False,True]:
 label='on' if enabled else 'off';job=base/label;job.mkdir();c=load(ROOT/'project.yaml');c['dataset']['duration_s']=30;c['monitor']['enabled']=enabled;c.update(_workspace=str(base),_task='monitor-'+label);atomic(job/'project.json',c)
 subprocess.run([install/'bin/vins','start',job],check=True,capture_output=True,text=True)
 self_cpu=0
 while True:
  s=json.loads((job/'state.json').read_text())
  try:
   stat=Path('/proc/'+str(s['pid'])+'/stat').read_text().split(') ',1)[1].split();self_cpu=max(self_cpu,(int(stat[11])+int(stat[12]))/os.sysconf('SC_CLK_TCK'))
  except OSError:pass
  if s['phase'] in ['completed','failed','cancelled']:break
  time.sleep(.5)
 assert s['phase']=='completed',s;assert (job/'files.json').is_file()
 s['supervisor_cpu_s_observed_lower_bound']=self_cpu;report[label]=s
atomic(ROOT/'evidence/v0.1/monitor-overhead.json',report);print('MONITOR PAIR COMPLETE')
