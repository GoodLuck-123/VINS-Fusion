#!/usr/bin/env bash
set -euo pipefail
source "$VINS_REMOTE_PAYLOAD/runtime_env.sh"
export VINS_BOARD_RUNTIME="$VINS_REMOTE_PAYLOAD"
python3 - <<'PY'
import hashlib,json,os,pathlib,re,shutil,signal,subprocess,sys,time,xmlrpc.client
root=pathlib.Path(os.environ['VINS_BOARD_RUNTIME'])
logs=pathlib.Path(os.environ['VINS_REMOTE_ROOT'])/'logs'
manifest=json.loads((root/'files.json').read_text())
for name,digest in manifest.items():
    if hashlib.sha256((root/name).read_bytes()).hexdigest()!=digest:
        raise RuntimeError('Runtime hash differs: '+name)
assert sys.version_info[:2]==(3,8),sys.version
import numpy,rosbag,rospy
from sensor_msgs.msg import Image,Imu
result=dict(verified_files=len(manifest),python=sys.version,python_executable=sys.executable,
            numpy=numpy.__version__,source=json.loads((root/'build_source.json').read_text()),bag_input=False)
(logs/'python_maps.txt').write_text(pathlib.Path('/proc/self/maps').read_text())
result['roslaunch_version']=subprocess.check_output(['rosversion','roslaunch'],text=True).strip()
binary=root/'.infra/vins_ws/devel/lib/vins/vins_node'
ldd=subprocess.check_output(['ldd',str(binary)],text=True)
(logs/'vins_ldd.txt').write_text(ldd)
assert 'not found' not in ldd and not re.search(r'libopencv_.*\.so\.4\.5',ldd)
original=root/'VINS-Fusion/config/euroc'
config=(original/'euroc_stereo_imu_config.yaml').read_text()
for key in ['output_path','pose_graph_save_path']:
    config=re.sub(r'^'+key+r':.*$',key+': "'+str(logs)+'"',config,flags=re.M)
(logs/'config.yaml').write_text(config)
for name in ['cam0_mei.yaml','cam1_mei.yaml']:shutil.copy2(original/name,logs/name)
os.environ['ROS_MASTER_URI']='http://127.0.0.1:11331'
master=xmlrpc.client.ServerProxy(os.environ['ROS_MASTER_URI'])
processes=[]
streams=[]
try:
    for name,command in [('roscore',['roscore','-p','11331']),('vins',[str(binary),str(logs/'config.yaml')])]:
        stream=(logs/(name+'.log')).open('w');streams.append(stream)
        process=subprocess.Popen(command,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
        processes.append((name,process))
        deadline=time.monotonic()+30
        while True:
            if process.poll() is not None:raise RuntimeError(name+' exited early: '+str(process.returncode))
            ready=False
            try:
                if name=='roscore':ready=master.getPid('/rk_runtime_probe')[0]==1
                else:
                    subscriptions={topic for topic,_ in master.getSystemState('/rk_runtime_probe')[2][1]}
                    ready={'/cam0/image_raw','/cam1/image_raw','/imu0'}<=subscriptions
            except OSError:pass
            if ready:break
            if time.monotonic()>deadline:raise TimeoutError(name+' readiness timeout')
            time.sleep(0.2)
        if name=='roscore':master.setParam('/rk_runtime_probe','/use_sim_time',True)
        else:
            maps=pathlib.Path('/proc/'+str(process.pid)+'/maps').read_text()
            (logs/'vins_maps.txt').write_text(maps)
            assert '.infra/runtime/lib/libopencv_core.so.4.2' in maps
            result['subscriptions_ready']=True
finally:
    for name,process in reversed(processes):
        if process.poll() is None:os.killpg(process.pid,signal.SIGINT)
        try:code=process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid,signal.SIGKILL);process.wait()
            raise TimeoutError(name+' shutdown timeout')
        result[name+'_exit_code']=code
    for stream in streams:stream.close()
assert result.get('subscriptions_ready') and result['roscore_exit_code']==0
if result['vins_exit_code']==-6:
    assert 'terminate called without an active exception' in (logs/'vins.log').read_text()
    result['cleanup_note']='Original ROS 1 unjoined sync thread abort retained, as in desktop reference'
else:assert result['vins_exit_code']==0
(logs/'validation.json').write_text(json.dumps(result,indent=2)+'\n')
print('ARM_ROS1_RUNTIME_OK hashes + private Python 3.8 imports + sensor subscriptions; cleanup exit recorded; no VIO input')
PY
