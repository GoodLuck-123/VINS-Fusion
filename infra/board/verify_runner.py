"""Real-board runner lifecycle tests; optional one complete bag replay."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('install',type=Path)
parser.add_argument('logs',type=Path)
parser.add_argument('bag',type=Path)
parser.add_argument('--full',action='store_true')
parser.add_argument('--expect-vins-exit',type=int,choices=[-6,0],default=-6)
args=parser.parse_args();root=args.install;logs=args.logs
sys.path.insert(0,str(Path(__file__).parent))
from install import install
install(root)
base=[str(root/'bin/run'),'--bag',str(args.bag)]
results={}
def run(name,options,expected):
    with (logs/(name+'.console.log')).open('w') as console:
        p=subprocess.run([*base,'--output',str(logs/name),*options],stdout=console,stderr=subprocess.STDOUT,timeout=500)
    assert p.returncode==expected,(name,p.returncode)
    report=json.loads((logs/name/'run.json').read_text())
    results[name]=dict(exit_code=p.returncode,report=report)
    return report
if args.full:
    report=run('full-replay',[],0 if args.expect_vins_exit==0 else 1)
    assert report['process_exits']==dict(vins=args.expect_vins_exit,roscore=0,playback=0),report
    assert report['status']==('completed' if args.expect_vins_exit==0 else 'failed'),report
    assert report['trajectory_poses']>=1800,report
else:
    output=logs/'cancelled'
    with (logs/'cancelled.console.log').open('w') as console:
        process=subprocess.Popen([*base,'--output',str(output)],stdout=console,stderr=subprocess.STDOUT)
        deadline=time.monotonic()+40
        while not (output/'vins.log').exists():
            assert process.poll() is None,'runner exited before VINS launch'
            assert time.monotonic()<deadline,'VINS launch timeout'
            time.sleep(.05)
        # A second run must not compete for the same project's ROS workload.
        other=subprocess.run([*base,'--output',str(logs/'conflict')],capture_output=True,text=True,timeout=30)
        assert other.returncode==1 and 'project lock' in other.stdout,other.stdout
        process.send_signal(signal.SIGINT)
        assert process.wait(timeout=25)==130
    cancelled=json.loads((output/'run.json').read_text())
    assert cancelled['status']=='cancelled',cancelled
    results['cancelled']=cancelled
    timeout=run('timeout',['--timeout','3'],124)
    assert timeout['status']=='failed'
    node=root/'bin/vins_node';backup=root/'bin/vins_node.validation-backup'
    assert not backup.exists();node.rename(backup)
    try:
        node.write_text('#!/bin/sh\nexit 7\n');node.chmod(0o755)
        failed=run('startup-failed',[],1)
        assert failed['process_exits']['vins']==7,failed
        assert not (logs/'startup-failed/playback.log').exists()
    finally:
        node.unlink();backup.rename(node)
    bad=subprocess.run([str(root/'bin/run'),'--bag',str(logs/'missing.bag'),'--output',str(logs/'missing-input')],capture_output=True,text=True)
    assert bad.returncode==1 and 'Missing file' in bad.stdout
    results['missing_bag_refused']=True
active=[]
for proc in Path('/proc').iterdir():
    if not proc.name.isdigit():continue
    try:
        argv=(proc/'cmdline').read_bytes().split(b'\0')
        if any(Path(v.decode(errors='replace')).name in ('vins_node','roscore','rosmaster') for v in argv[:2]):active.append(proc.name)
    except OSError:pass
assert not active,active
results['no_residual_ros']=True
(logs/'runner_summary.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps({key:('passed' if isinstance(value,dict) else value) for key,value in results.items()},indent=2))
