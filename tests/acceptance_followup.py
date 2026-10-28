"""Local batch runner: wait for final replay, inspect mappings, then verify faults."""
import json,shlex,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];target=sys.argv[1];log=ROOT/'build'/('final-'+target+'-run.log');deadline=time.monotonic()+1800
while '[replaying] euroc-final/' not in log.read_text(errors='replace'):
 text=log.read_text(errors='replace');assert '错误：' not in text,text[-2000:];assert time.monotonic()<deadline;time.sleep(1)
subprocess.run([ROOT/'.venv/bin/python',ROOT/'tests/runtime_maps.py',target],check=True)
while '[回收校验完成]' not in log.read_text(errors='replace'):
 text=log.read_text(errors='replace');assert '[failed]' not in text and '错误：' not in text,text[-2000:];assert time.monotonic()<deadline;time.sleep(1)
print('FINAL REPLAY PASSED',target,flush=True)
if target=='host':
 subprocess.run([ROOT/'.venv/bin/python',ROOT/'tests/package_checks.py'],check=True)
 r=json.loads((ROOT/'releases/host.json').read_text());install=Path(r['install'])
 for script,args in [('bag_endpoints.py',[]),('shutdown.py',[ROOT/'build/shutdown-validation']),('observer_inputs.py',[ROOT/'build/observer-validation'])]:
  text='source '+shlex.quote(str(install/'env.sh'))+' && python3 '+shlex.join([str(ROOT/'tests'/script),*map(str,args)])
  subprocess.run(['bash','-c',text],check=True)
 subprocess.run([ROOT/'.venv/bin/python',ROOT/'tests/lifecycle.py'],check=True)
 subprocess.run([ROOT/'.venv/bin/python',ROOT/'tests/monitor_overhead.py'],check=True)
else:subprocess.run([ROOT/'.venv/bin/python',ROOT/'tests/board_recovery.py'],check=True)
print('ACCEPTANCE FOLLOWUP COMPLETE',target,flush=True)
