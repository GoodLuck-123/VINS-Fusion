"""Real ROS messages: validate numeric/format/time counters without running VINS."""
import json,math,os,signal,socket,subprocess,sys,time,xmlrpc.client
from pathlib import Path
import rospy
from sensor_msgs.msg import Image,Imu
from nav_msgs.msg import Odometry
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'runtime'))
from common import atomic
base=Path(sys.argv[1]);base.mkdir(parents=True,exist_ok=True);install=Path(os.environ['VINS_INSTALL_ROOT']);children=[];logs=[]
with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
os.environ.update(ROS_MASTER_URI='http://127.0.0.1:'+str(port),ROS_HOME=str(base/'ros-home'),ROS_LOG_DIR=str(base/'ros-logs'))
def launch(name,args):
 f=(base/(name+'.log')).open('w');logs.append(f);p=subprocess.Popen(list(map(str,args)),stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True);children.append(p);return p
try:
 launch('master',['roscore','-p',port]);api=xmlrpc.client.ServerProxy(os.environ['ROS_MASTER_URI']);deadline=time.monotonic()+15
 while True:
  try:
   if api.getPid('/test')[0]==1:break
  except OSError:pass
  assert time.monotonic()<deadline;time.sleep(.2)
 out=base/'observation.json';launch('observer',[install/'bin/vins_observer','_width:=2','_height:=2','_output:='+str(out)])
 rospy.init_node('observer_test',disable_signals=True)
 cam=rospy.Publisher('/cam0/image_raw',Image,queue_size=10);imu=rospy.Publisher('/imu0',Imu,queue_size=10);pose=rospy.Publisher('/vins_estimator/odometry',Odometry,queue_size=10)
 while min(cam.get_num_connections(),imu.get_num_connections(),pose.get_num_connections())<1:
  assert time.monotonic()<deadline;time.sleep(.1)
 for i in range(3):
  t=rospy.Time(1 if i<2 else 2);a=Image();a.header.stamp=t;a.width=a.height=a.step=2;a.encoding='mono8' if i<2 else 'rgb8';a.data=b'1234' if i!=1 else b'123';cam.publish(a)
  b=Imu();b.header.stamp=t;b.angular_velocity.x=float('nan') if i==1 else 0;imu.publish(b)
  p=Odometry();p.header.stamp=t;p.pose.pose.orientation.w=1;p.pose.pose.position.x=float('nan') if i==1 else 0;pose.publish(p);time.sleep(.3)
 time.sleep(1);s=json.loads(out.read_text());assert [s[k]['count'] for k in ['image','imu','pose']]==[3,3,3],s
 assert [s[k]['invalid'] for k in ['image','imu','pose']]==[2,1,1],s
 assert all(s[k]['nonincreasing']==1 for k in ['image','imu','pose']),s
 atomic(ROOT/'evidence/v0.1/observer-inputs.json',s);print('OBSERVER INPUT CHECKS PASSED')
finally:
 rospy.signal_shutdown('test complete')
 for p in reversed(children):
  if p.poll() is None:os.killpg(p.pid,signal.SIGINT);p.wait(timeout=10)
 for f in logs:f.close()
