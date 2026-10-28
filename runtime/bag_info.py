"""Run in packaged ROS Python; inspect selected indexes and endpoint headers."""
import json,sys
import rosbag,rospy
c=json.load(open(sys.argv[1]));d=c['dataset'];topics={c['inputs']['camera']['topic']:'sensor_msgs/Image',c['inputs']['imu']['topic']:'sensor_msgs/Imu'}
with rosbag.Bag(d['bag']) as bag:
    indexes={}
    for topic,typ in topics.items():
        connections=list(bag._get_connections(topics=[topic]))
        if not connections or any(x.datatype!=typ for x in connections):raise ValueError('Missing/wrong topic type: '+topic)
        indexes[topic]=[x for x in bag._get_indexes(connections) if x]
        if not indexes[topic]:raise ValueError('Empty topic: '+topic)
    start=bag.get_start_time()+d['start_s'];selected_end=max(x[-1].time.to_sec() for lists in indexes.values() for x in lists)
    end=min(selected_end,start+d['duration_s']) if d['duration_s'] else selected_end
    if start>=end:raise ValueError('Dataset interval empty or past selected input EOF')
    info={}
    for topic,typ in topics.items():
        first=next(bag.read_messages(topics=[topic],start_time=rospy.Time.from_sec(start),end_time=rospy.Time.from_sec(end+.000001)),None)
        if first is None:raise ValueError('No selected messages: '+topic)
        # Other topics can outlive these inputs. Use the selected topic's own index.
        entries=[next((entry for entry in reversed(index) if entry.time.to_sec()<=end+.000001),None) for index in indexes[topic]]
        last_time=max(entry.time for entry in entries if entry is not None)
        last=next(bag.read_messages(topics=[topic],start_time=last_time,end_time=last_time+rospy.Duration(nsecs=1)))
        info[topic]={'type':typ,'first_ns':first.message.header.stamp.to_nsec(),'last_ns':last.message.header.stamp.to_nsec(),'bag_records_full_file':bag.get_message_count(topic_filters=[topic])}
        if info[topic]['first_ns']<=0 or info[topic]['last_ns']<=info[topic]['first_ns']:raise ValueError('Invalid topic timestamp endpoints: '+topic)
    camera=info[c['inputs']['camera']['topic']];imu=info[c['inputs']['imu']['topic']];td=c['vins']['td']*1e9
    if max(camera['first_ns']+td,imu['first_ns'])>=min(camera['last_ns']+td,imu['last_ns']):raise ValueError('Image/IMU time intervals do not overlap')
    print(json.dumps(dict(start_record_s=start,end_record_s=end,duration_s=end-start,topics=info)))
