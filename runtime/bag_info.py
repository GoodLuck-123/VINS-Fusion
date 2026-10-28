"""Private ROS inspection: indexed global origin, selected endpoints across split bags."""
import contextlib,json,sys
import rosbag,rospy
from common import dataset_files
c=json.load(open(sys.argv[1]));d=c['dataset'];topics={c['inputs']['camera']['topic']:'sensor_msgs/Image',c['inputs']['imu']['topic']:'sensor_msgs/Imu'}
with contextlib.ExitStack() as stack:
    bags=[stack.enter_context(rosbag.Bag(str(p))) for p in dataset_files(c)]
    origins=[];indexes={t:[] for t in topics}
    for bag in bags:
        origins += [index[0].time.to_sec() for index in bag._get_indexes(None) if index]
        for topic,typ in topics.items():
            connections=list(bag._get_connections(topics=[topic]))
            if any(x.datatype!=typ for x in connections):raise ValueError('Wrong topic type: '+topic)
            indexes[topic]+=[(bag,index) for index in bag._get_indexes(connections) if index]
    if any(not x for x in indexes.values()):raise ValueError('Missing/empty selected topics')
    # rosbag::View origin is min(all connection indexes), not chunk start time.
    start=min(origins)+d['start_s'];selected_end=max(index[-1].time.to_sec() for rows in indexes.values() for _,index in rows)
    end=min(selected_end,start+d['duration_s']) if d['duration_s'] else selected_end
    if start>=end:raise ValueError('Dataset interval empty or past selected input EOF')
    info={}
    for topic,typ in topics.items():
        firsts=[];lasts=[]
        for bag,index in indexes[topic]:
            first=next(bag.read_messages(topics=[topic],start_time=rospy.Time.from_sec(start),end_time=rospy.Time.from_sec(end+.000001)),None)
            if first is None:continue
            firsts.append(first)
            last_entry=next((x for x in reversed(index) if start<=x.time.to_sec()<=end+.000001),None)
            if last_entry is not None:lasts.append(next(bag.read_messages(topics=[topic],start_time=last_entry.time,end_time=last_entry.time+rospy.Duration(nsecs=1))))
        if not firsts or not lasts:raise ValueError('No selected messages: '+topic)
        first=min(firsts,key=lambda x:x.timestamp);last=max(lasts,key=lambda x:x.timestamp)
        info[topic]=dict(type=typ,first_ns=first.message.header.stamp.to_nsec(),last_ns=last.message.header.stamp.to_nsec(),bag_records_full_file=sum(b.get_message_count(topic_filters=[topic]) for b in bags))
        if info[topic]['first_ns']<=0 or info[topic]['last_ns']<=info[topic]['first_ns']:raise ValueError('Invalid topic timestamp endpoints: '+topic)
    camera=info[c['inputs']['camera']['topic']];imu=info[c['inputs']['imu']['topic']];td=c['vins']['td']*1e9
    if max(camera['first_ns']+td,imu['first_ns'])>=min(camera['last_ns']+td,imu['last_ns']):raise ValueError('Image/IMU time intervals do not overlap')
    print(json.dumps(dict(start_record_s=start,end_record_s=end,duration_s=end-start,topics=info,files=[p.name for p in dataset_files(c)])))
