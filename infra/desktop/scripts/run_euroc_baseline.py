"""Run untouched VINS against a complete EuRoC bag in a private ROS master."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import subprocess
import time
import xmlrpc.client

import rosbag


from workspace_paths import WORKSPACE_ROOT as ROOT
from process_metrics import ProcessMetrics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bag", type=Path, default=ROOT / "data/euroc/MH_01_easy.bag")
    parser.add_argument("--rate", type=float, default=1.0)
    parser.add_argument("--port", type=int, default=11321)
    parser.add_argument("--name", default=time.strftime("MH_01_easy_%Y%m%d_%H%M%S"))
    args = parser.parse_args()
    if args.rate <= 0 or args.rate > 1:
        parser.error("Use a rate in (0, 1] for the original reference")
    output = ROOT / "results/ros1" / args.name
    with rosbag.Bag(str(args.bag)) as bag:
        bag_duration = bag.get_end_time() - bag.get_start_time()
    with socket.socket() as check:
        check.bind(("127.0.0.1", args.port))
    output.mkdir(parents=True, exist_ok=False)
    os.environ.update(ROS_MASTER_URI=f"http://127.0.0.1:{args.port}", ROS_IP="127.0.0.1")
    original = ROOT / "VINS-Fusion/config/euroc"
    config = (original / "euroc_stereo_imu_config.yaml").read_text()
    config = re.sub(r'^output_path:.*$', f'output_path: "{output}"', config, flags=re.M)
    config = re.sub(r'^pose_graph_save_path:.*$', f'pose_graph_save_path: "{output}/pose_graph/"', config, flags=re.M)
    config_path = output / "euroc_stereo_imu_config.yaml"
    config_path.write_text(config)
    # Preserve calibration selection and all algorithm parameters from the repository.
    for calibration in ("cam0_mei.yaml", "cam1_mei.yaml"):
        shutil.copy2(original / calibration, output / calibration)
    monitor = None
    processes = []
    logs = []
    metadata = {"bag": str(args.bag.resolve()), "rate": args.rate,
                "source_commit": "be55a937a57436548ddfb1bd324bc1e9a9e828e0",
                "runner_commit": subprocess.check_output(
                    ["git", "-C", str(ROOT / "VINS-Fusion"), "rev-parse", "HEAD"], text=True).strip(),
                "config": str(config_path), "start_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "success": False}
    metadata["binary_sha256"] = hashlib.sha256((ROOT / ".infra/vins_ws/devel/lib/vins/vins_node").read_bytes()).hexdigest()
    metadata["bag_duration_s"] = bag_duration

    def launch(command, name):
        log = (output / f"{name}.log").open("w")
        logs.append(log)
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        processes.append((name, process))
        return process

    def assert_alive(process, name):
        if process.poll() is not None:
            raise RuntimeError(f"{name} exited with code {process.returncode}; see {output}")

    try:
        master_process = launch(["roscore", "-p", str(args.port)], "roscore")
        master = xmlrpc.client.ServerProxy(os.environ["ROS_MASTER_URI"])
        deadline = time.monotonic() + 30
        while True:
            assert_alive(master_process, "roscore")
            try:
                if master.getPid("/baseline_runner")[0] == 1:
                    break
            except OSError:
                pass
            if time.monotonic() > deadline:
                raise TimeoutError("ROS master did not become ready")
            time.sleep(0.25)
        master.setParam("/baseline_runner", "/use_sim_time", True)
        node = launch([str(ROOT / ".infra/vins_ws/devel/lib/vins/vins_node"), str(config_path)], "vins")
        deadline = time.monotonic() + 30
        required = {"/cam0/image_raw", "/cam1/image_raw", "/imu0"}
        while True:
            assert_alive(node, "vins_node")
            state = master.getSystemState("/baseline_runner")[2]
            subscribed = {topic for topic, _ in state[1]}
            if required <= subscribed:
                break
            if time.monotonic() > deadline:
                raise TimeoutError("VINS sensor subscriptions did not become ready")
            time.sleep(0.25)
        monitor = ProcessMetrics(node.pid, output / "resource_details.csv")
        playback = launch(["rosbag", "play", "--clock", "--rate", str(args.rate), "--delay", "3",
                           "--topics", "/cam0/image_raw", "/cam1/image_raw", "/imu0",
                           "--bags", str(args.bag.resolve())], "playback")
        start = time.monotonic()
        samples = []
        with (output / "resource_samples.csv").open("w") as resource:
            resource.write("wall_s,rss_kib,cpu_ticks\n")
            while playback.poll() is None:
                assert_alive(node, "vins_node")
                if time.monotonic() - start > bag_duration / args.rate + 120:
                    raise TimeoutError("Playback exceeded expected duration")
                monitor.sample()
                stat = Path(f"/proc/{node.pid}/stat").read_text().split()
                cpu_ticks = int(stat[13]) + int(stat[14])
                status = Path(f"/proc/{node.pid}/status").read_text()
                rss = int(re.search(r"VmRSS:\s+(\d+)", status).group(1))
                samples.append(rss)
                resource.write(f"{time.monotonic()-start:.3f},{rss},{cpu_ticks}\n")
                resource.flush()
                time.sleep(1)
        if playback.returncode != 0:
            raise RuntimeError(f"rosbag play failed: {playback.returncode}")
        metadata["playback_wall_s"] = time.monotonic() - start
        metadata["peak_sampled_rss_kib"] = max(samples, default=0)
        # Allow the original asynchronous backend to drain, then check output stops growing.
        trajectory = output / "vio.csv"
        previous = -1
        stable = 0
        deadline = time.monotonic() + 60
        while stable < 5:
            assert_alive(node, "vins_node")
            monitor.sample()
            current = trajectory.stat().st_size if trajectory.exists() else 0
            stable = stable + 1 if current == previous else 0
            previous = current
            if time.monotonic() > deadline:
                raise TimeoutError("VINS output did not settle after replay")
            time.sleep(1)
        rows = [line for line in trajectory.read_text().splitlines() if line.strip()]
        if len(rows) < 100:
            raise RuntimeError(f"Insufficient trajectory output: {len(rows)} poses")
        metadata["trajectory_poses"] = len(rows)
        metadata["first_timestamp_ns"] = int(rows[0].split(",")[0])
        metadata["last_timestamp_ns"] = int(rows[-1].split(",")[0])
        metadata["resources"] = monitor.summary()
        metadata["success"] = True
        print(json.dumps(metadata, indent=2), flush=True)
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
        metadata["note"] = "Unmodified ROS 1 node has an unjoined sync thread; shutdown exit is recorded separately from playback success."
        (output / "run.json").write_text(json.dumps(metadata, indent=2) + "\n")


if __name__ == "__main__":
    main()
