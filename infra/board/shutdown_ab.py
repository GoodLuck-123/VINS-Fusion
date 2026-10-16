"""Serial same-runner A/B; sample each owned process, keep all exit states."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('baseline',type=Path);ap.add_argument('candidate',type=Path);ap.add_argument('bag',type=Path);ap.add_argument('output',type=Path)
args=ap.parse_args();out=args.output;cases={}

def process_table():
    table={}
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():continue
        try:
            stat=(p/'stat').read_text().rsplit(')',1)[1].split()
            cmd=(p/'cmdline').read_bytes().split(b'\0')
            table[int(p.name)]=(int(stat[1]),cmd,(int(stat[11])+int(stat[12]))/os.sysconf('SC_CLK_TCK'))
        except (OSError,ValueError,IndexError):pass
    return table

def sample(parent):
    table=process_table();owned={parent}
    while True:
        more={pid for pid,(ppid,_,_) in table.items() if ppid in owned}
        if more<=owned:break
        owned|=more
    rows=[]
    for pid in owned:
        if pid not in table:continue
        _,cmd,cpu=table[pid];label=' '.join(c.decode(errors='replace') for c in cmd[:3])
        row=dict(pid=pid,command=label,cpu_all_threads_s=cpu,rss_kib=0,pss_kib=None)
        try:
            for line in Path('/proc',str(pid),'status').read_text().splitlines():
                if line.startswith('VmRSS:'):row['rss_kib']=int(line.split()[1])
            for line in Path('/proc',str(pid),'smaps_rollup').read_text().splitlines():
                if line.startswith('Pss:'):row['pss_kib']=int(line.split()[1])
            rows.append(row)
        except OSError:pass
    return rows

for name,root,expected in [('baseline',args.baseline,1),('candidate',args.candidate,0)]:
    target=out/name
    assert not target.exists()
    with (out/(name+'.console.log')).open('w') as console,(out/(name+'-resources.jsonl')).open('w') as metrics:
        p=subprocess.Popen([str(root/'bin/run'),'--bag',str(args.bag),'--output',str(target)],stdout=console,stderr=subprocess.STDOUT)
        peak={};start=time.monotonic()
        try:
            while p.poll() is None:
                assert time.monotonic()-start<480,'Runner timeout'
                for row in sample(p.pid):
                    row['elapsed_s']=time.monotonic()-start;metrics.write(json.dumps(row)+'\n')
                    current=peak.setdefault(str(row['pid']),dict(command=row['command'],last_sample_cpu_all_threads_s=0,peak_rss_kib=0,peak_pss_kib=None))
                    current['last_sample_cpu_all_threads_s']=max(current['last_sample_cpu_all_threads_s'],row['cpu_all_threads_s'])
                    current['peak_rss_kib']=max(current['peak_rss_kib'],row['rss_kib'])
                    if row['pss_kib'] is not None:current['peak_pss_kib']=max(current['peak_pss_kib'] or 0,row['pss_kib'])
                metrics.flush();time.sleep(.5)
        finally:
            if p.poll() is None:p.terminate();p.wait(timeout=25)
    assert p.returncode==expected,(name,p.returncode)
    report=json.loads((target/'run.json').read_text())
    expected_exits=dict(vins=-6 if name=='baseline' else 0,playback=0,roscore=0)
    assert report['process_exits']==expected_exits,report
    assert report['status']==('failed' if name=='baseline' else 'completed'),report
    log=(target/'vins.log').read_text()
    assert log.count('Initialization finish!')==1,log.count('Initialization finish!')
    assert 'failure detection' not in log.lower() and 'throw img' not in log
    assert report['trajectory_poses']==1831 and report['last_timestamp_ns']==1403636763813555456,report
    cases[name]=dict(binary_sha256=hashlib.sha256((root/'bin/vins_node').read_bytes()).hexdigest(),cli_exit_code=p.returncode,run=report,initializations=1,no_reset_or_pair_drop=True,resources_by_pid=peak,resource_scope='0.5s /proc samples of runner descendants; last CPU sample is a lower bound, RSS/PSS per process, not simultaneous sums; DDR/power unavailable')
    print('[AB_CASE_FINISHED]',name,report['process_exits'],flush=True)
    time.sleep(3)
assert (args.baseline/'scripts/cli/run.py').read_bytes()==(args.candidate/'scripts/cli/run.py').read_bytes()
assert not any(Path(v.decode(errors='replace')).name in ('vins_node','roscore','rosmaster') for _,cmd,_ in process_table().values() for v in cmd[:2])
result=dict(status='pass',cases=cases,candidate_binary_sha256=cases['candidate']['binary_sha256'],candidate_library_sha256=hashlib.sha256((args.candidate/'runtime/lib/libvins_lib.so').read_bytes()).hexdigest(),no_residual_ros=True)
(out/'ab_summary.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({name:dict(exits=value['run']['process_exits'],poses=value['run']['trajectory_poses']) for name,value in cases.items()},indent=2))
