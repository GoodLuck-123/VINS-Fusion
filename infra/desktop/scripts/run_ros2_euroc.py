"""Replay EuRoC on ROS 2 with unchanged VIO configuration and resource sampling."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import time

import rclpy
from rclpy.node import Node

from process_metrics import ProcessMetrics
from workspace_paths import REPO_ROOT, WORKSPACE_ROOT as ROOT


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--rate", type=float, default=1)
    args = parser.parse_args()
    if not 0 < args.rate <= 1:
        parser.error("Use a replay rate in (0, 1]")
    output = ROOT / "results/ros2" / args.name
    output.mkdir(parents=True, exist_ok=False)
    original = REPO_ROOT / "config/euroc"
    config = (original / "euroc_stereo_imu_config.yaml").read_text()
    for key, value in (("output_path", str(output)), ("pose_graph_save_path", str(output / "pose_graph"))):
        config = re.sub(rf'^{key}:.*$', f'{key}: "{value}"', config, flags=re.M)
    config_path = output / "euroc_stereo_imu_config.yaml"
    config_path.write_text(config)
    for name in ("cam0_mei.yaml", "cam1_mei.yaml"):
        shutil.copy2(original / name, output / name)
    qos = output / "playback_qos.yaml"
    qos.write_text("\n".join(f"{topic}:\n  reliability: reliable\n  history: keep_last\n  depth: {depth}\n  durability: volatile"
                             for topic, depth in (("/cam0/image_raw", 100), ("/cam1/image_raw", 100), ("/imu0", 2000))) + "\n")
    binary = ROOT / ".infra/ros2_ws/install/lib/vins/vins_node"
    metadata = {"success": False, "rate": args.rate, "mode": "stereo_imu_vio",
                "source_commit": subprocess.check_output(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"], text=True).strip(),
                "source_modified": bool(subprocess.check_output(["git", "-C", str(REPO_ROOT), "diff", "--", "camera_models", "vins_estimator", "loop_fusion", "global_fusion", "ros2"], text=True).strip()),
                "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
                "ros_domain_id": os.environ.get("ROS_DOMAIN_ID"),
                "start_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    bag = ROOT / "data/euroc/MH_01_easy_ros2"
    processes, logs = [], []
    monitor = None
    rclpy.init()
    observer = Node("baseline_observer")

    def launch(command, name):
        log = (output / f"{name}.log").open("w")
        logs.append(log)
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        processes.append((name, process))
        return process

    def alive(process):
        if process.poll() is not None:
            raise RuntimeError(f"Process exited {process.returncode}; see {output}")

    try:
        node = launch([str(binary), str(config_path), "--ros-args", "-p", "use_sim_time:=true"], "vins")
        deadline = time.monotonic() + 30
        while not all(observer.count_subscribers(topic) >= 1 for topic in ("/cam0/image_raw", "/cam1/image_raw", "/imu0")):
            alive(node)
            rclpy.spin_once(observer, timeout_sec=0.2)
            if time.monotonic() > deadline:
                raise TimeoutError("Sensor subscriptions did not become ready")
        monitor = ProcessMetrics(node.pid, output / "resource_samples.csv")
        playback = launch(["ros2", "bag", "play", str(bag), "--rate", str(args.rate), "--clock", "100",
                           "--delay", "3", "--qos-profile-overrides-path", str(qos)], "playback")
        start = time.monotonic()
        while playback.poll() is None:
            alive(node)
            monitor.sample()
            if time.monotonic() - start > 310 / args.rate:
                raise TimeoutError("Playback exceeded expected duration")
            time.sleep(1)
        metadata["playback_wall_s"] = time.monotonic() - start
        if playback.returncode != 0:
            raise RuntimeError(f"Replay failed: {playback.returncode}")
        trajectory = output / "vio.csv"
        previous, stable = -1, 0
        deadline = time.monotonic() + 60
        drain_start = time.monotonic()
        while stable < 5:
            alive(node)
            monitor.sample()
            size = trajectory.stat().st_size if trajectory.exists() else 0
            stable = stable + 1 if previous == size else 0
            previous = size
            if time.monotonic() > deadline:
                raise TimeoutError("Backend did not settle")
            time.sleep(1)
        metadata["settling_wait_s"] = time.monotonic() - drain_start
        metadata["resources"] = monitor.summary()
        metadata["peak_sampled_rss_kib"] = metadata["resources"]["peak_sampled_rss_kib"]
        rows = [row for row in trajectory.read_text().splitlines() if row.strip()]
        metadata["trajectory_poses"] = len(rows)
        metadata["first_timestamp_ns"] = int(rows[0].split(",")[0])
        metadata["last_timestamp_ns"] = int(rows[-1].split(",")[0])
        expected = json.loads((ROOT / "results/ros2/bag_conversion.json").read_text())["ros2"]["/cam0/image_raw"]["last_header_ns"]
        if len(rows) < 100 or abs(metadata["last_timestamp_ns"] - expected) > 1_000_000:
            raise RuntimeError("Incomplete trajectory coverage")
        metadata["success"] = True
    finally:
        for name, process in reversed(processes):
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGINT)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGTERM)
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait()
            metadata[f"{name}_exit_code"] = process.returncode
        if monitor:
            monitor.close()
        for log in logs:
            log.close()
        sensor_counts = re.search(r"sensor_counts img0=(\d+) img1=(\d+) imu=(\d+) processed=(\d+)",
                                  (output / "vins.log").read_text())
        if sensor_counts:
            metadata["sensor_counts"] = dict(zip(("img0", "img1", "imu", "processed"), map(int, sensor_counts.groups())))
        if metadata["success"] and (metadata.get("vins_exit_code") != 0 or not sensor_counts
                                    or list(map(int, sensor_counts.groups())) != [3682, 3682, 36820, 3682]):
            metadata["success"] = False
            metadata["failure"] = "Unclean shutdown or incomplete sensor processing"
        observer.destroy_node()
        rclpy.shutdown()
        (output / "run.json").write_text(json.dumps(metadata, indent=2) + "\n")
        print(json.dumps(metadata, indent=2))
    if not metadata["success"]:
        raise RuntimeError(f"Experiment validation failed: {output}")


if __name__ == "__main__":
    main()
