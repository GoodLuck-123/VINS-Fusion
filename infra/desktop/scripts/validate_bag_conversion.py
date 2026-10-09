"""Compare every common sensor field and timestamp across ROS 1 / ROS 2 bags."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from rosbags.highlevel import AnyReader


def fingerprint(path):
    output = {}
    with AnyReader([path]) as reader:
        for connection, recorded_ns, raw in reader.messages():
            msg = reader.deserialize(raw, connection.msgtype)
            topic = connection.topic
            if topic not in ("/cam0/image_raw", "/cam1/image_raw", "/imu0"):
                continue
            row = output.setdefault(topic, {"count": 0, "sha": hashlib.sha256(), "serialized_bytes": 0})
            header_ns = msg.header.stamp.sec * 1_000_000_000 + msg.header.stamp.nanosec
            row["sha"].update(struct.pack("<qq", recorded_ns, header_ns))
            row["sha"].update(msg.header.frame_id.encode() + b"\0")
            if topic == "/imu0":
                values = [msg.orientation.x, msg.orientation.y, msg.orientation.z, msg.orientation.w,
                          msg.angular_velocity.x, msg.angular_velocity.y, msg.angular_velocity.z,
                          msg.linear_acceleration.x, msg.linear_acceleration.y, msg.linear_acceleration.z]
                for covariance in (msg.orientation_covariance, msg.angular_velocity_covariance,
                                   msg.linear_acceleration_covariance):
                    values.extend(covariance)
                row["sha"].update(struct.pack("<" + "d" * len(values), *values))
            else:
                row["sha"].update(struct.pack("<IIII", msg.height, msg.width, msg.step, msg.is_bigendian))
                row["sha"].update(msg.encoding.encode() + b"\0")
                row["sha"].update(msg.data.tobytes())
            row["count"] += 1
            row["serialized_bytes"] += len(raw)
            row.setdefault("first_header_ns", header_ns)
            row["last_header_ns"] = header_ns
    for row in output.values():
        row["sensor_fields_sha256"] = row.pop("sha").hexdigest()
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("ros1", type=Path)
    parser.add_argument("ros2", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source, converted = fingerprint(args.ros1), fingerprint(args.ros2)
    if set(source) != set(converted) or len(source) != 3:
        raise RuntimeError("Sensor topic sets differ")
    for topic in source:
        for key in ("count", "first_header_ns", "last_header_ns", "sensor_fields_sha256"):
            if source[topic][key] != converted[topic][key]:
                raise RuntimeError(f"Conversion changed {topic}: {key}")
    report = {"success": True, "ros1": source, "ros2": converted,
              "scope": "All sensor fields incl. image pixels, IMU covariances, frame IDs, header and recorded times; ROS 1 Header.seq excluded (removed in ROS 2)."}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
