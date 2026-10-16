"""Run with the private ROS Python; inspect a bag without starting ROS nodes."""
import json
import math
import sys


def inspect(path, required, td, full):
    import rosbag
    import genpy
    expected_md5 = {'sensor_msgs/Image': '060021388200f6f0f447d0fcd9c64743', 'sensor_msgs/Imu': '6a62c6daae103f4ff57a132d6f95cec2'}
    topics = {}
    with rosbag.Bag(path, 'r', allow_unindexed=False) as bag:
        info = bag.get_type_and_topic_info()
        connections = list(bag._get_connections())  # Check every connection, not only the merged topic summary.
        start, end = bag.get_start_time(), bag.get_end_time()
        if not math.isfinite(start) or not math.isfinite(end) or end <= start:
            raise ValueError('Bag is empty or its record time interval is invalid')
        for topic, expected in required.items():
            item = info.topics.get(topic)
            if item is None or not item.message_count:
                raise ValueError('Missing or empty topic: ' + topic)
            if item.msg_type != expected:
                raise ValueError('{}: expected {}, got {}'.format(topic, expected, item.msg_type))
            for connection in connections:
                if connection.topic == topic and (connection.datatype != expected or connection.md5sum != expected_md5[expected]):
                    raise ValueError('Incompatible connection type/MD5: ' + topic)
            first = next(bag.read_messages(topics=[topic]))
            # Seek a short tail using the public time filter. Never deserialize
            # the entire image stream merely to find its last header.
            window = min(1.0, end-start)
            last = None
            while last is None:
                for message in bag.read_messages(topics=[topic], start_time=genpy.Time.from_sec(max(start, end-window))):
                    last = message
                window *= 2
                if window > 2*(end-start)+2 and last is None:
                    raise ValueError('Cannot read final message: ' + topic)
            first_ns, last_ns = first.message.header.stamp.to_nsec(), last.message.header.stamp.to_nsec()
            if first_ns <= 0 or last_ns < first_ns:
                raise ValueError('Invalid header endpoints at {}: {}, {}'.format(topic, first_ns, last_ns))
            topics[topic] = dict(type=expected, count=item.message_count, first_ns=first_ns, last_ns=last_ns)
        if full:
            previous, counts = {}, dict.fromkeys(required, 0)
            for topic, message, _ in bag.read_messages(topics=list(required)):
                stamp = message.header.stamp.to_nsec()
                if stamp <= 0 or stamp <= previous.get(topic, -1):
                    raise ValueError('Non-positive, repeated or backwards header stamp: {} at {}'.format(topic, stamp))
                previous[topic] = stamp
                counts[topic] += 1
            for topic in required:
                if counts[topic] != topics[topic]['count']:
                    raise ValueError('Read/index count differs: ' + topic)
        intervals = []
        for topic, item in topics.items():
            offset = int(round(td*1e9)) if item['type'] == 'sensor_msgs/Image' else 0
            intervals.append((item['first_ns']+offset, item['last_ns']+offset))
        overlap = (max(a for a, _ in intervals), min(b for _, b in intervals))
        if overlap[0] >= overlap[1]:
            raise ValueError('Image/IMU header intervals have no positive overlap (image + td)')
        return dict(path=path, duration_s=end-start, topics=topics, overlap_ns=overlap, timestamp_scan='all headers, strictly increasing' if full else 'first/last headers only; interior timestamps not scanned')


def main():
    try:
        print(json.dumps(inspect(sys.argv[1], json.loads(sys.argv[2]), float(sys.argv[3]), sys.argv[4]=='full')))
    except Exception as error:
        print('{}: {}'.format(type(error).__name__, error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
