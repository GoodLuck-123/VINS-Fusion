"""Run independent, serial EuRoC transport repeats; notify only on terminal events."""
import argparse
import csv
import fcntl
import hashlib
import itertools
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import statistics
import subprocess
import sys
import time

from process_metrics import host_snapshot, percentile
from workspace_paths import REPO_ROOT, WORKSPACE_ROOT

SCRIPTS = REPO_ROOT / "infra/desktop/scripts"
RESULTS = WORKSPACE_ROOT / "results/ros2"
TRANSPORTS = ("ros", "memfd", "vgem")
MODES = ("stereo_imu", "mono_imu")
ORDERS = (TRANSPORTS, ("memfd", "vgem", "ros"), ("vgem", "ros", "memfd"),
          ("vgem", "memfd", "ros"), ("memfd", "ros", "vgem"), ("ros", "vgem", "memfd"))
METRICS = ("cpu_s", "vins_cpu_s", "source_cpu_s", "playback_wall_s", "ate_rmse_m",
           "rpe_rmse_m", "vins_pss_mib", "source_pss_mib", "vins_rss_mib", "source_rss_mib", "pool_waits")


def utc():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    temporary.replace(path)


def schedule(batch, repetitions):
    trials = []
    for repeat in range(1, repetitions + 1):
        modes = MODES if repeat % 2 else tuple(reversed(MODES))
        for mode in modes:
            for transport in ORDERS[(repeat - 1) % len(ORDERS)]:
                trials.append(dict(index=len(trials) + 1, repeat=repeat, mode=mode, transport=transport,
                                   name=f"{batch}_{mode.split('_')[0]}_{transport}_r{repeat:02d}"))
    return trials


def frozen_files(extra_paths=()):
    install = WORKSPACE_ROOT / ".infra/ros2_ws/install/lib"
    paths = [install / "libvins_component.so", install / "libvins_euroc_component.so",
             install / "vins/vins_node", install / "vins/euroc_player_node",
             REPO_ROOT / "infra/desktop/cyclonedds_wsl.xml"]
    tracked = subprocess.check_output(["git", "ls-files", "-z", "camera_models", "vins_estimator",
                                       "loop_fusion", "global_fusion", "ros2", "config/euroc", "infra/desktop/scripts",
                                       "infra/desktop/uv.lock"], cwd=REPO_ROOT).decode().split("\0")
    paths.extend(REPO_ROOT / p for p in tracked if p)
    paths.extend(Path(p) for p in extra_paths)
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(paths))}


def active_native_processes():
    found = []
    for directory in Path("/proc").iterdir():
        if not directory.name.isdigit():
            continue
        try:
            executable = (directory / "exe").resolve(strict=True)
            if executable.name in ("vins_node", "euroc_player_node", "component_container"):
                found.append(dict(pid=int(directory.name), executable=str(executable)))
        except (OSError, RuntimeError):
            pass
    return found


def assert_quiet():
    active = active_native_processes()
    if active:
        raise RuntimeError(f"Another VINS/player/container is active: {active}")


def execute(command, log_path, env, timeout):
    """Wait locally without model/API polling; signal the runner to clean up on timeout."""
    with log_path.open("w") as log:
        process = subprocess.Popen(command, cwd=REPO_ROOT, env=env, stdout=log,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        try:
            code = process.wait(timeout=timeout)
        except BaseException:
            for sig, grace in ((signal.SIGINT, 35), (signal.SIGTERM, 10), (signal.SIGKILL, 5)):
                if process.poll() is not None:
                    break
                os.killpg(process.pid, sig)
                try:
                    process.wait(timeout=grace)
                except subprocess.TimeoutExpired:
                    continue
            raise
    if code:
        raise RuntimeError(f"Command exited {code}: {log_path}")


def collect(trial):
    directory = RESULTS / trial["name"]
    run = json.loads((directory / "run.json").read_text())
    evaluation = json.loads((directory / "evaluation.json").read_text())
    if not run["success"] or run.get("vins_exit_code") != 0 or run.get("playback_exit_code") != 0:
        raise RuntimeError(f"Incomplete run: {directory}")
    if (run["mode"] != trial["mode"] + "_vio" or run["image_transport"] != trial["transport"] or
            run["deployment"] != "split" or run["image_mode"] != "share" or run["rate"] != 1 or
            run["rmw"] != "rmw_cyclonedds_cpp" or run["source_modified"]):
        raise RuntimeError(f"Unexpected trial configuration: {directory}")
    counts = dict(img0=3682, img1=3682 if trial["mode"] == "stereo_imu" else 0, imu=36820, processed=3682)
    if run["sensor_counts"] != counts or evaluation["matched_estimate_fraction"] < 0.95:
        raise RuntimeError(f"Incomplete sensor/trajectory coverage: {directory}")
    log = (directory / "vins.log").read_text()
    if "failure detection" in log or "throw img" in log:
        raise RuntimeError(f"Tracking failure or pairing drop: {directory}")
    if not run["pixel_timestamp_sha256"]["source_matches_consumer"]:
        raise RuntimeError(f"Pixel verification failed: {directory}")
    if trial["transport"] != "ros":
        writer, reader = run["shared_writer"], run["shared_reader"]
        if writer["outstanding"] or writer["failed"] or reader["failed"] or reader["verified"] != sum(list(counts.values())[:2]):
            raise RuntimeError(f"Buffer ownership/verification failed: {directory}")
    resources, source = run["resources"], run["source_resources"]
    return dict(**trial, cpu_s=run["combined_cpu_time_s"], vins_cpu_s=resources["cpu_time_s"],
                source_cpu_s=source["cpu_time_s"], playback_wall_s=run["playback_wall_s"],
                ate_rmse_m=evaluation["ate_translation_m"]["rmse"], rpe_rmse_m=evaluation["rpe_translation_m_one_pose_step"]["rmse"],
                vins_pss_mib=resources["peak_sampled_pss_kib"] / 1024,
                source_pss_mib=source["peak_sampled_pss_kib"] / 1024,
                vins_rss_mib=resources["peak_sampled_rss_kib"] / 1024,
                source_rss_mib=source["peak_sampled_rss_kib"] / 1024,
                pool_waits=run.get("shared_writer", {}).get("waits", 0),
                poses=run["trajectory_poses"], matched_poses=evaluation["matched_poses"],
                pixel_timestamp_sha256=run["pixel_timestamp_sha256"],
                control={key:run.get(key) for key in ("vins_component_sha256", "player_component_sha256",
                         "binary_sha256", "player_binary_sha256", "dds_profile_sha256", "source_commit", "verification")})


def validate_controls(records):
    if len({json.dumps(row["control"], sort_keys=True) for row in records}) != 1:
        raise RuntimeError("Source/binary/profile/verification controls differ")
    for mode in MODES:
        signatures = {json.dumps(row["pixel_timestamp_sha256"], sort_keys=True) for row in records if row["mode"] == mode}
        if len(signatures) > 1:
            raise RuntimeError(f"Inputs differ within {mode}")


def distribution(values):
    return dict(n=len(values), median=statistics.median(values), min=min(values), max=max(values),
                q25=percentile(values, 0.25), q75=percentile(values, 0.75))


def summarize(state, directory):
    records = state["completed"]
    validate_controls(records)
    groups = []
    for mode, transport in itertools.product(MODES, TRANSPORTS):
        subset = [row for row in records if row["mode"] == mode and row["transport"] == transport]
        if len(subset) != state["repetitions"]:
            raise RuntimeError(f"Expected {state['repetitions']} valid trials for {mode}/{transport}")
        metrics = {key:distribution([row[key] for row in subset]) for key in METRICS}
        paired = []
        for row in subset:
            baseline = next(r for r in records if r["mode"] == mode and r["transport"] == "ros" and r["repeat"] == row["repeat"])
            paired.append(100 * (row["cpu_s"] / baseline["cpu_s"] - 1))
        groups.append(dict(mode=mode, transport=transport, metrics=metrics, paired_cpu_change_percent=distribution(paired)))
    summary = dict(batch=state["batch"], n=len(records), groups=groups, controls=records[0]["control"],
                   inputs_identical_per_mode=True, scope="Two native processes including threads; SHA256 enabled; serial full MH01 playback. No DDR/power measurement.")
    write_json(directory / "summary.json", summary)
    fields = ["index", "repeat", "mode", "transport", "name", *METRICS, "poses", "matched_poses"]
    with (directory / "trials.csv").open("w") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader(); writer.writerows(records)
    lines = [f"## EuRoC 串行重复实验：{state['batch']}", "",
             f"新增 {len(records)} 次完整实验：单目/双目，各传输独立重复 {state['repetitions']} 次；不包含此前六次试跑。",
             "每轮仅一个数据源和一个 VINS；上一轮完成、退出、评估后再启动下一轮。顺序轮换，每轮间隔 " + str(state["cooldown_s"]) + " 秒。",
             "同一冻结二进制、MH_01_easy 输入/标定、1 倍目标供给、Cyclone DDS 小分片配置、share 入口和全像素 SHA256 校验；无回环/RViz。", "",
             "| 模式 | 传输 | n | 合计 CPU 秒中位数 [Q25, Q75] | CPU 秒范围 | 回放秒中位数 | ATE RMSE 中位数 (m) | 同轮对照 CPU 变化中位数 |",
             "| --- | --- | ---: | --- | --- | ---: | ---: | ---: |"]
    for group in groups:
        m, c = group["metrics"], group["metrics"]["cpu_s"]
        lines.append(f"| {group['mode']} | {group['transport']} | {c['n']} | {c['median']:.2f} [{c['q25']:.2f}, {c['q75']:.2f}] | {c['min']:.2f}–{c['max']:.2f} | {m['playback_wall_s']['median']:.2f} | {m['ate_rmse_m']['median']:.6f} | {group['paired_cpu_change_percent']['median']:+.2f}% |")
    lines += ["", "CPU 秒是数据源与 VINS 所有线程累计 CPU 时间之和；负的对照变化表示省 CPU。回放墙钟含启动与完成通知观察，目标 1 倍不能保证无背压。",
              "五轮顺序轮换缓解顺序偏差，但不构成完全平衡设计；未固定宿主频率/温度，不能据此宣称统计显著或外推 RK3588。",
              "原始 CSV/summary.json 还记录两进程分别的 CPU、RSS/PSS 峰值、池满等待与 ATE/RPE；两个独立 PSS 峰值不能相加当作同时峰值。",
              "每轮原始资源采样含 WSL 主机负载和 PSI；宿主指标包含其他程序，不是 Windows 全机观测。SHA256 校验的线程位置随路径不同，结果包含校验成本。",
              "各轮完整处理、干净退出、全像素/时间戳一致和共享槽位归还均已通过；DDR 流量和功耗未实测。", ""]
    (directory / "summary.md").write_text("\n".join(lines))
    return summary


def archive(state, directory):
    report = REPO_ROOT / "docs/ROS1_ROS2_COMPARISON.md"
    marker = f"<!-- experiment:{state['batch']} -->"
    original = report.read_text()
    if marker in original:
        raise RuntimeError("Batch already appended to comparison report")
    snapshot = REPO_ROOT / "infra/desktop/comparison_reference" / state["batch"]
    snapshot.mkdir(exist_ok=False)
    public_state = {key:value for key,value in state.items() if key not in ("completion_hook",)}
    public_state["status"] = "complete"
    write_json(snapshot / "batch.json", public_state)
    for name in ("summary.json", "summary.md", "trials.csv", "native_environment.json"):
        shutil.copy2(directory / name, snapshot / name)
    for trial in state["completed"]:
        source = RESULTS / trial["name"]
        destination = snapshot / source.name
        destination.mkdir()
        for name in ("run.json", "evaluation.json", "vio.csv", "resource_samples.csv", "source_resource_samples.csv",
                     "cyclonedds.xml", f"euroc_{trial['mode']}_config.yaml", "cam0_mei.yaml", "cam1_mei.yaml"):
            shutil.copy2(source / name, destination / name)
        logs = (source / "vins.log").read_text() + "\n" + (source / "playback.log").read_text()
        evidence = [line for line in logs.splitlines() if any(key in line for key in
                    ("image_ingress ", "sensor_counts ", "replay_counts ", "shared_peer ", "shared_buffer ", "shared_writer ", "shared_reader ", "image_digest "))]
        (destination / "ingress_evidence.log").write_text("\n".join(evidence) + "\n")
    checksums = [f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(snapshot)}" for p in sorted(snapshot.rglob('*')) if p.is_file()]
    (snapshot / "SHA256SUMS").write_text("\n".join(checksums) + "\n")
    report.write_text(original + "\n" + marker + "\n" + (directory / "summary.md").read_text() +
                      f"\n[本轮 {len(state['completed'])} 次实验快照](../infra/desktop/comparison_reference/{state['batch']}/)。\n")
    assert report.read_text().startswith(original)


def notify(state, directory):
    event = dict(batch=state["batch"], status=state["status"], completed=len(state["completed"]),
                 total=len(state["trials"]), failure=state.get("failure"), directory=str(directory), utc=utc())
    write_json(directory / "event.json", event)
    if state["completion_hook"]:
        try:
            execute([*state["completion_hook"], str(directory / "event.json")], directory / "hook.log", os.environ.copy(), 30)
            state["notification"] = "hook_exited_zero"
        except Exception as error:
            state["notification"] = str(error)
        write_json(directory / "state.json", state)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", required=True)
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--cooldown", type=float, default=10)
    parser.add_argument("--completion-hook", type=Path, help="JSON file containing an argv array; event.json path is appended")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.batch) or args.repetitions < 1 or args.cooldown < 0:
        parser.error("Invalid batch name, repetitions or cooldown")
    trials = schedule(args.batch, args.repetitions)
    if args.dry_run:
        print(json.dumps(trials, indent=2)); return
    RESULTS.mkdir(parents=True, exist_ok=True)
    with (RESULTS / ".shared_repeats.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        directory = RESULTS / args.batch
        directory.mkdir(exist_ok=False)
        hook = json.loads(args.completion_hook.read_text()) if args.completion_hook else []
        if not isinstance(hook, list) or not all(isinstance(item, str) for item in hook):
            raise ValueError("Completion hook must be a JSON argv array")
        state = dict(batch=args.batch, status="preflight", pid=os.getpid(), start_utc=utc(),
                     repetitions=args.repetitions, cooldown_s=args.cooldown, trials=trials, completed=[], completion_hook=hook)
        write_json(directory / "state.json", state)
        env = os.environ.copy()
        env["VINS_RMW_IMPLEMENTATION"] = "rmw_cyclonedds_cpp"
        env["CYCLONEDDS_URI"] = "file://" + str(REPO_ROOT / "infra/desktop/cyclonedds_wsl.xml")
        evaluation_env = os.environ.copy()
        evaluation_env["UV_CACHE_DIR"] = str(WORKSPACE_ROOT / ".infra/uv-cache")
        try:
            assert_quiet()
            with open("/dev/dri/card0", "r+b", buffering=0):
                pass
            dirty = subprocess.check_output(["git", "status", "--porcelain"], cwd=REPO_ROOT, text=True)
            if dirty:
                raise RuntimeError("Commit the reviewed runner/plan before starting the frozen batch")
            state["source_commit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()
            source_env = "set -e\nsource " + shlex.quote(str(SCRIPTS / "ros2_env.sh")) + "\nexec "
            execute(["bash", "-c", source_env + shlex.join(["python", str(SCRIPTS / "verify_ros2_environment.py")])],
                    directory / "environment.log", env, 90)
            shutil.copy2(RESULTS / "native_environment.json", directory / "native_environment.json")
            native = json.loads((directory / "native_environment.json").read_text())
            libraries = set()
            for target in native["targets"].values():
                for line in target["ldd"]:
                    if "=>" in line:
                        path = line.split("=>", 1)[1].strip().split()[0]
                        if "/.infra/" in path:
                            libraries.add(path)
            state["loaded_sdk_libraries"] = sorted(libraries)
            state["frozen_files"] = frozen_files(libraries)
            for trial in trials:
                assert_quiet()
                if frozen_files(libraries) != state["frozen_files"]:
                    raise RuntimeError("Frozen source/binary/profile changed during the batch")
                state.update(status="running", current=trial, host_before=host_snapshot())
                write_json(directory / "state.json", state)
                print(f"{utc()} START {trial['index']}/{len(trials)} {trial['name']}", flush=True)
                command = ["python", str(SCRIPTS / "run_ros2_euroc.py"), "--name", trial["name"],
                           "--mode", trial["mode"], "--deployment", "split", "--image-mode", "share",
                           "--image-transport", trial["transport"]]
                execute(["bash", "-c", source_env + shlex.join(command)], directory / (trial["name"] + ".log"), env, 440)
                assert_quiet()
                execute(["uv", "run", "--offline", "--project", str(REPO_ROOT / "infra/desktop"), "--locked", "python",
                         str(SCRIPTS / "evaluate_baseline.py"), str(RESULTS / trial["name"]), "--label", trial["name"]],
                        directory / (trial["name"] + "_evaluation.log"), evaluation_env, 90)
                record = collect(trial)
                record.update(host_before=state["host_before"], host_after=host_snapshot(), completed_utc=utc())
                state["completed"].append(record)
                validate_controls(state["completed"])
                if frozen_files(libraries) != state["frozen_files"]:
                    raise RuntimeError("Frozen source/binary/profile changed during replay")
                write_json(directory / "state.json", state)
                print(f"{utc()} DONE CPU={record['cpu_s']:.2f}s ATE={record['ate_rmse_m']:.6f}m", flush=True)
                if trial["index"] != len(trials):
                    time.sleep(args.cooldown)
            state["status"] = "archiving"
            summarize(state, directory)
            archive(state, directory)
            state.update(status="complete", end_utc=utc())
            write_json(directory / "state.json", state)
        except BaseException as error:
            state.update(status="failed", failure=f"{type(error).__name__}: {error}", end_utc=utc(),
                         remaining_processes=active_native_processes())
            write_json(directory / "state.json", state)
            print(state["failure"], file=sys.stderr, flush=True)
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)
            notify(state, directory)
        if state["status"] != "complete":
            raise SystemExit(1)


if __name__ == "__main__":
    main()
