import os, json, time, signal, subprocess, socket, xmlrpc.client, termios, math
from pathlib import Path
work=Path('/tmp/vins-platform-intake-imu'); work.mkdir(exist_ok=False)
fd=os.open('/dev/ttyS7',os.O_RDONLY|os.O_NOCTTY|os.O_NONBLOCK); original=termios.tcgetattr(fd); os.close(fd)
s=socket.socket(); s.bind(('127.0.0.1',0)); port=s.getsockname()[1]; s.close()
env=os.environ.copy(); env.update(ROS_MASTER_URI='http://127.0.0.1:%s'%port,ROS_IP='127.0.0.1',ROS_HOME=str(work/'ros'),ROS_LOG_DIR=str(work/'roslogs'))
os.environ.update(env)
children=[]; handles=[]; report={'probe':'existing_gnw500_ros_driver','workspace':str(work),'master_port':port,'requested_imu_rate':200,'baud':115200,'seconds':8}
def launch(name,args):
 f=(work/(name+'.log')).open('w'); handles.append(f)
 p=subprocess.Popen(args,env=env,stdout=f,stderr=subprocess.STDOUT,start_new_session=True,stdin=subprocess.DEVNULL); children.append((name,p)); return p
stats={'count':0,'finite':0,'nonincreasing_stamp':0,'seq_gaps':0,'first_stamp':None,'last_stamp':None,'first_arrival':None,'last_arrival':None,'acc_norm_sum':0.,'max_arrival_gap_s':0.,'sample':None}; lastseq=None
try:
 master=launch('master',['/opt/ros/noetic/bin/roscore','-p',str(port)])
 deadline=time.monotonic()+15
 while True:
  try:
   if xmlrpc.client.ServerProxy(env['ROS_MASTER_URI']).getPid('/vins_intake')[0]==1: break
  except OSError: pass
  if master.poll() is not None or time.monotonic()>deadline: raise RuntimeError('master not ready')
  time.sleep(.15)
 import rospy
 from sensor_msgs.msg import Imu
 rospy.init_node('vins_intake_monitor',anonymous=True,disable_signals=True)
 def observe(m):
  global lastseq
  t=m.header.stamp.to_nsec(); a=time.monotonic(); values=[m.linear_acceleration.x,m.linear_acceleration.y,m.linear_acceleration.z,m.angular_velocity.x,m.angular_velocity.y,m.angular_velocity.z]
  if stats['last_stamp'] is not None and t<=stats['last_stamp']: stats['nonincreasing_stamp']+=1
  if stats['last_arrival'] is not None: stats['max_arrival_gap_s']=max(stats['max_arrival_gap_s'],a-stats['last_arrival'])
  if lastseq is not None: stats['seq_gaps']+=max(0,m.header.seq-lastseq-1)
  lastseq=m.header.seq
  stats['count']+=1; stats['finite']+=int(all(math.isfinite(v) for v in values)); stats['acc_norm_sum']+=math.sqrt(sum(v*v for v in values[:3]))
  if stats['first_stamp'] is None: stats['first_stamp']=t; stats['first_arrival']=a; stats['sample']={'frame_id':m.header.frame_id,'values':values}
  stats['last_stamp']=t; stats['last_arrival']=a
 sub=rospy.Subscriber('/vins_intake/imu',Imu,observe,queue_size=200)
 imu=launch('imu',['/home/firefly/driver_ws/devel/lib/gnw_500/gnw_ahrs','__name:=vins_intake_imu','_port:=/dev/ttyS7','_baudrate:=115200','_imu_rate:=200','_topic:=/vins_intake/imu','_frame:=imu_link'])
 time.sleep(8)
 sub.unregister(); rospy.signal_shutdown('probe finished')
 report['observed']=stats
 if stats['count']>1:
  report['arrival_hz']=(stats['count']-1)/(stats['last_arrival']-stats['first_arrival'])
  report['header_hz']=(stats['count']-1)*1e9/(stats['last_stamp']-stats['first_stamp'])
  report['mean_acceleration_norm']=stats['acc_norm_sum']/stats['count']
except BaseException as e: report['error']=repr(e)
finally:
 exits={}
 for name,p in reversed(children):
  forced=[]
  for sig,seconds in [(signal.SIGINT,5),(signal.SIGTERM,2),(signal.SIGKILL,2)]:
   if p.poll() is not None: break
   os.killpg(p.pid,sig)
   if sig!=signal.SIGINT: forced.append(int(sig))
   try: p.wait(timeout=seconds)
   except subprocess.TimeoutExpired: pass
  exits[name]={'exit_code':p.poll(),'escalated_signals':forced}
 report['process_exits']=exits
 for f in handles: f.close()
 fd=os.open('/dev/ttyS7',os.O_RDONLY|os.O_NOCTTY|os.O_NONBLOCK); termios.tcsetattr(fd,termios.TCSANOW,original); os.close(fd)
 report['serial_settings_restored']=True
 (work/'report.json').write_text(json.dumps(report,indent=2)+'\n'); print(json.dumps(report,indent=2))
