"""Real no-input/IMU-wait SIGINT checks, using only a relocatable package."""
import json,os,signal,socket,subprocess,sys,time,xmlrpc.client
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'runtime'))
from common import atomic,load,effective
install=Path(os.environ['VINS_INSTALL_ROOT']);base=Path(sys.argv[1]);base.mkdir(parents=True,exist_ok=True);report={}
for name in ['no-input','imu-wait']:
 job=base/name;job.mkdir();c=load(ROOT/'project.yaml');effective(c,job)
 with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
 env=dict(os.environ,ROS_MASTER_URI='http://127.0.0.1:'+str(port),ROS_HOME=str(job/'ros-home'),ROS_LOG_DIR=str(job/'ros-logs'))
 children=[];logs=[]
 def launch(key,args):
  f=(job/(key+'.log')).open('w');logs.append(f);p=subprocess.Popen(list(map(str,args)),env=env,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True);children.append((key,p));return p
 try:
  master=launch('master',['roscore','-p',port]);api=xmlrpc.client.ServerProxy(env['ROS_MASTER_URI']);deadline=time.monotonic()+15
  while True:
   try:
    if api.getPid('/test')[0]==1:break
   except OSError:pass
   assert time.monotonic()<deadline,'master not ready';time.sleep(.2)
  api.setParam('/test','/use_sim_time',True);node=launch('vins',[install/'bin/vins_node',job/'vins.yaml'])
  deadline=time.monotonic()+15
  while '/vins_estimator' not in dict(api.getSystemState('/test')[2][1]).get('/cam0/image_raw',[]):
   assert time.monotonic()<deadline,'vins subscription not ready';time.sleep(.2)
  if name=='imu-wait':
   launch('playback',['rosbag','play','--clock','--duration','8','--topics','/cam0/image_raw','--bags',c['dataset']['bag']]);time.sleep(5)
   assert node.poll() is None
  else:time.sleep(1)
  os.killpg(node.pid,signal.SIGINT);code=node.wait(timeout=10);assert code==0,(name,code)
  report[name]={'vins_exit':code,'log_bytes':(job/'vins.log').stat().st_size}
 finally:
  for key,p in reversed(children):
   if p.poll() is None:
    os.killpg(p.pid,signal.SIGINT)
    try:p.wait(timeout=10)
    except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
  for f in logs:f.close()
atomic(base/'report.json',report);print(json.dumps(report))
