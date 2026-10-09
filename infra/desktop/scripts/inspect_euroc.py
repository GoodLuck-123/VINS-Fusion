"""Inspect ROS 1 sensor data without importing ROS or the native environment."""
import argparse
import json
from pathlib import Path

from rosbags.rosbag1 import Reader
from rosbags.typesys import Stores, get_typestore


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("bag", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    store = get_typestore(Stores.ROS1_NOETIC)
    with Reader(args.bag) as reader:
        report = {
            "bag": str(args.bag.resolve()),
            "duration_s": reader.duration / 1e9,
            "connections": [
                {"topic": c.topic, "type": c.msgtype, "count": c.msgcount}
                for c in reader.connections
            ],
            "first_sensor_messages": {},
            "last_sensor_header_timestamps_ns": {},
        }
        wanted = {"/cam0/image_raw", "/cam1/image_raw", "/imu0"}
        sensors = [c for c in reader.connections if c.topic in wanted]
        for connection, stamp, raw in reader.messages(connections=sensors):
            if connection.topic in report["first_sensor_messages"]:
                continue
            msg = store.deserialize_ros1(raw, connection.msgtype)
            item = {"bag_timestamp_ns": stamp,
                    "header_timestamp_ns": msg.header.stamp.sec * 10**9 + msg.header.stamp.nanosec}
            if connection.msgtype == "sensor_msgs/msg/Image":
                item.update(width=msg.width, height=msg.height, encoding=msg.encoding,
                            step=msg.step, data_bytes=len(msg.data))
            report["first_sensor_messages"][connection.topic] = item
            if wanted <= report["first_sensor_messages"].keys():
                break
        for connection, _, raw in reader.messages(connections=sensors, start=reader.end_time - 10 * 10**9):
            msg = store.deserialize_ros1(raw, connection.msgtype)
            report["last_sensor_header_timestamps_ns"][connection.topic] = (
                msg.header.stamp.sec * 10**9 + msg.header.stamp.nanosec)
    missing = wanted - report["first_sensor_messages"].keys()
    if missing:
        raise RuntimeError(f"Missing EuRoC sensor topics: {sorted(missing)}")
    for topic in ("/cam0/image_raw", "/cam1/image_raw"):
        image = report["first_sensor_messages"][topic]
        if (image["width"], image["height"], image["encoding"]) != (752, 480, "mono8"):
            raise RuntimeError(f"Unexpected EuRoC image format: {topic}: {image}")
    text = json.dumps(report, indent=2)
    print(text)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n")


if __name__ == "__main__":
    main()
