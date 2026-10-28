"""Closed-bag validation in the package's private ROS/Python runtime."""
import json,math
from common import camera_settings
from pathlib import Path

def inspect(job,config):
    import rosbag
    raw=Path(job)/'raw';bags=sorted(raw.glob('*.bag'))
    if list(raw.glob('*.active')):raise ValueError('录包未正常关闭，保留 .active 文件供恢复')
    if not bags:raise ValueError('录包未生成 bag：'+str(raw))
    cam=config['inputs']['camera'];hw=camera_settings(config);imu=config['inputs']['imu'];required={cam['topic']:'sensor_msgs/Image',imu['topic']:'sensor_msgs/Imu',hw['raw_topic']:'sensor_msgs/Image',hw['metadata_topic']:'std_msgs/UInt64MultiArray',imu['device']['raw_topic']:'std_msgs/UInt8MultiArray'}
    counts={t:0 for t in required};stamps={};dimensions={};invalid=0
    for path in bags:
        with rosbag.Bag(str(path)) as bag:
            for topic,msg,record_time in bag.read_messages(topics=list(required)):
                if msg._type!=required[topic]:raise ValueError('录包消息类型错误：'+topic)
                counts[topic]+=1
                if hasattr(msg,'header'):
                    stamp=msg.header.stamp.to_nsec();prev=stamps.get(topic,{})
                    if stamp<=prev.get('last_ns',0):invalid+=1
                    stamps[topic]=dict(first_ns=prev.get('first_ns',stamp),last_ns=stamp)
                if msg._type=='sensor_msgs/Image':
                    expected=(cam['width'],cam['height']) if topic==cam['topic'] else (hw['width'],hw['height'])
                    dimensions[topic]=[msg.width,msg.height,msg.encoding]
                    if (msg.width,msg.height)!=expected or msg.encoding!='mono8' or len(msg.data)<msg.step*msg.height:invalid+=1
                if topic==imu['topic']:
                    if not all(math.isfinite(x) for x in [msg.linear_acceleration.x,msg.linear_acceleration.y,msg.linear_acceleration.z,msg.angular_velocity.x,msg.angular_velocity.y,msg.angular_velocity.z]):invalid+=1
    if any(not x for x in counts.values()) or invalid:raise ValueError('录包不完整或数据异常：'+json.dumps(dict(counts=counts,invalid=invalid)))
    if counts[cam['topic']]!=counts[hw['raw_topic']] or counts[cam['topic']]!=counts[hw['metadata_topic']]:raise ValueError('处理图、原图及 metadata 录包数量不一致')
    return dict(bags=[p.name for p in bags],counts=counts,timestamps=stamps,dimensions=dimensions,invalid=invalid,header_clock='host receive/parse',camera_trigger='IMU external Line0' if hw['trigger']=='hardware' else 'free run',absolute_accuracy_verified=False)
