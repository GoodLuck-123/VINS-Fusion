"""Board tests: stop without data, single-thread mode, and IMU-starved backend."""
import argparse
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import xmlrpc.client

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('install',type=Path);parser.add_argument('bag',type=Path);parser.add_argument('output',type=Path)
args=parser.parse_args();root=args.install;out=args.output;out.mkdir()
sys.path.insert(0,str(root/'scripts/cli'))
from common import configuration,prepare_config,environment
from run import Transport
results=[]
for name,single,starved in [('no-input',False,False),('single-thread',True,False),('imu-starved',False,True)]:
    folder=out/name;folder.mkdir()
    config=configuration(root/'config/euroc/euroc_stereo_imu_config.yaml',root,folder)
    actual=prepare_config(config,folder)
    if single:actual.write_text(actual.read_text().replace('multiple_thread: 1','multiple_thread: 0'))
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    env=environment(root);env.update(ROS_MASTER_URI='http://127.0.0.1:'+str(port),ROS_IP='127.0.0.1',ROS_LOG_DIR=str(folder/'ros-logs'))
    processes=[];logs=[];observed=False;exits={};errors=[]
    def launch(name,command):
        stream=(folder/(name+'.log')).open('w');logs.append(stream)
        p=subprocess.Popen(command,env=env,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True);processes.append((name,p));return p
    def wait_for(predicate,seconds=20):
        deadline=time.monotonic()+seconds
        while True:
            assert all(p.poll() is None for _,p in processes),[(n,p.returncode) for n,p in processes]
            try:
                if predicate():return
            except OSError:pass
            if time.monotonic()>deadline:raise TimeoutError(name+' readiness')
            time.sleep(.05)
    try:
        master=launch('roscore',['roscore','-p',str(port)])
        rpc=xmlrpc.client.ServerProxy(env['ROS_MASTER_URI'],transport=Transport())
        wait_for(lambda:rpc.getPid('/shutdown_probe')[0]==1)
        node=launch('vins',['stdbuf','-oL','-eL',str(root/'bin/vins_node'),str(actual)])
        wait_for(lambda:set(config['topics'])<={t for t,ns in rpc.getSystemState('/shutdown_probe')[2][1] if '/vins_estimator' in ns})
        if starved:
            publisher='''import sys,time,rosbag,rospy
from sensor_msgs.msg import Image
rospy.init_node('shutdown_image_source',disable_signals=True)
pubs={t:rospy.Publisher(t,Image,queue_size=100) for t in ['/cam0/image_raw','/cam1/image_raw']}
end=time.monotonic()+10
while not all(p.get_num_connections() for p in pubs.values()):
 if time.monotonic()>end:raise TimeoutError('image publisher connection')
 time.sleep(.05)
with rosbag.Bag(sys.argv[1]) as bag:
 for i,(topic,msg,_) in enumerate(bag.read_messages(topics=list(pubs))):
  pubs[topic].publish(msg);time.sleep(.025)
  if i>=39:break
time.sleep(.5)
'''
            result=subprocess.run(['python3','-c',publisher,str(args.bag)],env=env,capture_output=True,text=True,timeout=20)
            (folder/'publisher.log').write_text(result.stdout+result.stderr);assert result.returncode==0
            wait_for(lambda:'wait for imu' in (folder/'vins.log').read_text(),10);observed=True
        start=time.monotonic();os.killpg(node.pid,signal.SIGINT);node_exit=node.wait(timeout=5)
        shutdown_s=time.monotonic()-start
        assert node_exit==0,(name,node_exit)
    finally:
        for label,process in reversed(processes):
            if process.poll() is None:
                os.killpg(process.pid,signal.SIGINT)
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid,signal.SIGKILL);process.wait();errors.append(label+' required SIGKILL')
            exits[label]=process.returncode
        for stream in logs:stream.close()
    assert not errors and all(v==0 for v in exits.values()),(errors,exits)
    results.append(dict(case=name,process_exits=exits,imu_wait_observed=observed,shutdown_s=shutdown_s))
(out/'summary.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps(results,indent=2))
