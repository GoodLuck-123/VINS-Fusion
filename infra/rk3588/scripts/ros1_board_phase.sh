#!/usr/bin/env bash
set -euo pipefail
runtime=$(/usr/bin/python3 -c 'import json,os,pathlib; p=json.loads((pathlib.Path(os.environ["VINS_REMOTE_PAYLOAD"])/"plan.json").read_text()); print((pathlib.Path.home()/pathlib.Path(p["runtime"]).expanduser()).resolve())')
source "$runtime/runtime_env.sh"
export VINS_BOARD_RUNTIME="$runtime"
python3 - <<'PY'
import hashlib,json,os,pathlib,shutil,subprocess,threading,time
payload=pathlib.Path(os.environ['VINS_REMOTE_PAYLOAD'])
logs=pathlib.Path(os.environ['VINS_REMOTE_ROOT'])/'logs'
root=pathlib.Path(os.environ['VINS_BOARD_RUNTIME'])
plan=json.loads((payload/'plan.json').read_text())
manifest_file=root/'files.json'
assert hashlib.sha256(manifest_file.read_bytes()).hexdigest()==plan['runtime_manifest_sha256']
manifest=json.loads(manifest_file.read_text())
def verify_runtime():
    for name,digest in manifest.items():
        if hashlib.sha256((root/name).read_bytes()).hexdigest()!=digest:
            raise RuntimeError('Runtime changed: '+name)
verify_runtime()
bag=(pathlib.Path.home()/pathlib.Path(plan['bag']).expanduser()).resolve()
digest=hashlib.sha256()
with bag.open('rb') as stream:
    for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
assert digest.hexdigest()==plan['bag_sha256']
import rosbag
with rosbag.Bag(str(bag)) as reader:
    counts={topic:reader.get_message_count(topic_filters=[topic]) for topic in ['/cam0/image_raw','/cam1/image_raw','/imu0']}
assert counts=={'/cam0/image_raw':3682,'/cam1/image_raw':3682,'/imu0':36820}
link=root/'data/euroc/MH_01_easy.bag'
link.parent.mkdir(parents=True,exist_ok=True)
if link.is_symlink():assert link.resolve()==bag
elif link.exists():raise RuntimeError('Refusing to overwrite runtime bag')
else:link.symlink_to(bag)
shutil.copy2(payload/'plan.json',logs/'plan.json')
state=dict(status='running',bag_hash_verified=True,bag_input_counts=counts,
           count_scope='Bag records only, not node receive counters',runtime_files_verified=len(manifest))
(logs/'state.json').write_text(json.dumps(state,indent=2)+'\n')
stop=threading.Event()
def telemetry():
    paths=sorted([*pathlib.Path('/sys/class/thermal').glob('thermal_zone*/temp'),
                  *pathlib.Path('/sys/devices/system/cpu/cpufreq').glob('policy*/scaling_cur_freq'),
                  *pathlib.Path('/sys/class/devfreq').glob('*dmc*/cur_freq')])
    with (logs/'telemetry.jsonl').open('w') as stream:
        while not stop.is_set():
            values={}
            for p in paths:
                try:values[str(p)]=p.read_text().strip()
                except OSError:values[str(p)]=None
            stream.write(json.dumps(dict(monotonic_s=time.monotonic(),values=values))+'\n');stream.flush()
            stop.wait(1)
sampler=threading.Thread(target=telemetry)
sampler.start()
output=root/'results/ros1'/plan['name']
try:
    command=['python3',str(root/'VINS-Fusion/infra/desktop/scripts/run_euroc_baseline.py'),
             '--bag',str(bag),'--name',plan['name'],'--port','11321','--rate','1']
    (logs/'driver-command.json').write_text(json.dumps(command,indent=2)+'\n')
    with (logs/'runner.log').open('w') as log:
        code=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT).returncode
    if code:raise RuntimeError('Original runner exit '+str(code))
    run=json.loads((output/'run.json').read_text())
    assert run['success'] and run['trajectory_poses']==1831
    assert run['playback_exit_code']==run['roscore_exit_code']==0
    assert abs(run['last_timestamp_ns']-1403636763813555500)<=512
    text=(output/'vins.log').read_text()
    assert text.count('Initialization finish!')==1
    assert 'failure detection' not in text and 'throw img' not in text
    if run['vins_exit_code']==-6:
        assert 'terminate called without an active exception' in text
        state['cleanup_note']='Original ROS 1 unjoined sync thread abort retained; not a clean VINS exit'
    else:assert run['vins_exit_code']==0
    verify_runtime()
    state.update(status='complete',vins_exit_code=run['vins_exit_code'],trajectory_poses=run['trajectory_poses'])
except BaseException as error:
    state.update(status='failed',failure=type(error).__name__+': '+str(error))
    raise
finally:
    stop.set();sampler.join()
    if output.exists():shutil.copytree(output,logs/plan['name'])
    (logs/'state.json').write_text(json.dumps(state,indent=2)+'\n')
PY
