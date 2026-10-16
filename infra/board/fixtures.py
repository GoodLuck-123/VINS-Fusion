"""Create tiny actual ROS1 bags with controlled type and timestamp failures."""
from pathlib import Path
import sys
import rosbag
import genpy
from sensor_msgs.msg import Image, Imu
from std_msgs.msg import String

folder=Path(sys.argv[1]);folder.mkdir()
for name in ['valid','missing-imu','wrong-type','no-overlap','duplicate','backwards']:
    with rosbag.Bag(str(folder/(name+'.bag')),'w') as bag:
        for i in range(6):
            record=genpy.Time.from_sec(10+i*.1)
            for topic in ['/cam0/image_raw','/cam1/image_raw','/imu0']:
                if name=='missing-imu' and topic=='/imu0':continue
                if name=='wrong-type' and topic=='/imu0':message=String(data='not an IMU')
                else:
                    message=Imu() if topic=='/imu0' else Image(height=1,width=1,encoding='mono8',step=1,data=b'\0')
                    stamp=10+i*.1
                    if topic=='/imu0' and name=='no-overlap':stamp+=100
                    if topic=='/imu0' and i==3 and name=='duplicate':stamp=10.2
                    if topic=='/imu0' and i==3 and name=='backwards':stamp=10.1
                    message.header.stamp=genpy.Time.from_sec(stamp)
                bag.write(topic,message,t=record)
print('Created',folder)
