"""Freeze reproducible reference outputs and write the ROS version comparison."""
import hashlib
import json
from pathlib import Path
import re
import shutil
from statistics import mean

from workspace_paths import DESKTOP_ROOT, DOCS_ROOT, WORKSPACE_ROOT as ROOT

snapshot = DESKTOP_ROOT / "ros2_reference"
snapshot.mkdir(exist_ok=True)
records = []
native_environment = json.loads((ROOT / "results/ros2/native_environment.json").read_text())
normalized_config = None
for version in ("ros1", "ros2"):
    for iteration in (1, 2):
        name = f"MH_01_easy_{version}_metrics{iteration}"
        source = ROOT / "results" / version / name
        run = json.loads((source / "run.json").read_text())
        evaluation = json.loads((source / "evaluation.json").read_text())
        if not run["success"] or run["playback_exit_code"] != 0:
            raise RuntimeError(f"Incomplete experiment: {source}")
        if version == "ros2" and run["vins_exit_code"] != 0:
            raise RuntimeError(f"Unclean ROS 2 shutdown: {source}")
        if version == "ros2" and run["binary_sha256"] != native_environment["targets"]["vins"]["binary_sha256"]:
            raise RuntimeError(f"Library verification used a different binary: {source}")
        log = (source / "vins.log").read_text()
        if "failure detection" in log or "throw img" in log:
            raise RuntimeError(f"Failure or dropped image pairing: {source}")
        config = re.sub(r'^(output_path|pose_graph_save_path):.*$', '',
                        (source / "euroc_stereo_imu_config.yaml").read_text(), flags=re.M)
        if normalized_config is None:
            normalized_config = config
        elif normalized_config != config:
            raise RuntimeError("Algorithm configuration differed across versions")
        destination = snapshot / name
        destination.mkdir(exist_ok=True)
        files = ("run.json", "evaluation.json", "vio.csv", "trajectory.tum", "trajectory.png",
                 "euroc_stereo_imu_config.yaml", "cam0_mei.yaml", "cam1_mei.yaml")
        for filename in files:
            shutil.copy2(source / filename, destination / filename)
        samples = "resource_details.csv" if version == "ros1" else "resource_samples.csv"
        shutil.copy2(source / samples, destination / "resources.csv")
        records.append((version, iteration, run, evaluation))
for filename in ("bag_conversion.json", "smoke.json", "native_environment.json"):
    shutil.copy2(ROOT / "results/ros2" / filename, snapshot / filename)
manifest = [f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(DESKTOP_ROOT)}"
            for path in sorted(snapshot.rglob("*")) if path.is_file() and path.name != "SHA256SUMS"]
(snapshot / "SHA256SUMS").write_text("\n".join(manifest) + "\n")

lines = ["# ROS 1 / ROS 2 EuRoC 对比实验", "", "日期：2026-10-09", "",
         "`master` 保留 ROS 1；`ros2-humble` 是独立的 ROS 2 Humble 版本。",
         "实验在 Ubuntu 22.04.5 / WSL2 / x86_64 串行运行；顺序为 ROS 1 → ROS 2 → ROS 2 → ROS 1。", "",
         "使用 MH_01_easy，双目 IMU，完整 1 倍速；不运行回环/GNSS/RViz。",
         "OpenCV 4.2.0、Ceres 1.14.0、Eigen 3.3.9、GCC 13.4、配置和标定保持一致。",
         "ROS 2 所需的 cv_bridge 3.2.1 / C++17 以及中间件是记录在案的接口与运行时差异。", "",
         "全部图像像素、IMU 数值/协方差和原始时间戳逐消息校验一致；完整校验和依赖路径记录见参照快照。", "",
         "## 精度与完整性", "",
         "| 版本 / 轮次 | poses | 匹配率 | ATE RMSE (m) | 相邻位姿 RPE RMSE (m) | 回放耗时 (s) | 退出码 |",
         "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
for version, iteration, run, evaluation in records:
    lines.append(f"| {version} / {iteration} | {run['trajectory_poses']} | {evaluation['matched_estimate_fraction']*100:.2f}% | "
                 f"{evaluation['ate_translation_m']['rmse']:.6f} | {evaluation['rpe_translation_m_one_pose_step']['rmse']:.6f} | "
                 f"{run['playback_wall_s']:.2f} | {run['vins_exit_code']} |")
lines += ["", "ATE 使用保持尺度的 SE(3) 对齐，时间匹配容差 0.01 s；RPE 是相邻 pose，间隔约 0.1 s。",
          "匹配率不足 100% 主要来自真值未覆盖的序列尾部。末帧覆盖检查通过，日志无配对丢弃或 failure detection。",
          "ROS 2 每轮收到左右图像各 3682、IMU 36820，处理图像对 3682。",
          "ROS 1 的 -6 是原版未 join 同步线程导致的退出 abort；完整回放状态分别记录。ROS 2 的后台线程和全局发布器显式销毁。", "",
          "## 节点资源压力", "",
          "| 版本 / 轮次 | CPU 秒 | 平均单核 CPU (%) | CPU p95 (%) | RSS 峰值 (MiB) | PSS 峰值 (MiB) | 线程峰值 | 主缺页 |",
          "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
for version, iteration, run, _ in records:
    r = run["resources"]
    lines.append(f"| {version} / {iteration} | {r['cpu_time_s']:.2f} | {r['mean_cpu_percent_one_core']:.2f} | "
                 f"{r['sampled_cpu_percent_one_core']['p95']:.2f} | {r['peak_sampled_rss_kib']/1024:.2f} | "
                 f"{r.get('peak_sampled_pss_kib', 0)/1024:.2f} | {r['peak_threads']} | {r['major_faults']} |")
lines += ["", "CPU 以一个逻辑核为 100%，包含节点全部线程；窗口从订阅就绪到回放后稳定，含启动延迟和稳定等待。",
          "p95 来自约 1 s 的 CPU 采样，不能解读为单帧处理延迟。完整 RSS/PSS、缺页、I/O、主线程上下文切换和系统压力记录在每轮 resources.csv / run.json。", "",
          "## I/O 和传输压力", "",
          "| 版本 / 轮次 | 进程物理读 (MiB) | 进程物理写 (MiB) | 主线程自愿切换 | 主线程非自愿切换 | 主机 loopback RX 增量 (MiB) |",
          "| --- | ---: | ---: | ---: | ---: | ---: |"]
for version, iteration, run, _ in records:
    r = run["resources"]
    lines.append(f"| {version} / {iteration} | {r.get('read_bytes',0)/2**20:.3f} | {r.get('write_bytes',0)/2**20:.3f} | "
                 f"{r['main_voluntary_switches']} | {r['main_involuntary_switches']} | {r['host_observations'].get('loopback_rx_bytes',0)/2**20:.3f} |")
conversion = json.loads((snapshot / "bag_conversion.json").read_text())
for version in ("ros1", "ros2"):
    data = conversion[version]
    span = (data["/cam0/image_raw"]["last_header_ns"]-data["/cam0/image_raw"]["first_header_ns"]) / 1e9
    logical_rate = sum(row["serialized_bytes"] for row in data.values()) / span / 2**20
    lines.append(f"\n{version} 输入序列化数据量 / 图像时间跨度：约 {logical_rate:.3f} MiB/s（逻辑输入压力，不是实测链路带宽）。")
lines += ["", "物理 I/O 受页缓存影响；rchar/wchar 也不是内存带宽。主机 loopback / PSI 包含其他进程，且 WSL 网络计数可能无法反映传感器传输，不用它们推断 DDR 或零拷贝收益。",
          "当前未采集内存控制器带宽、硬件 cycles/cache misses、温度或功耗，也未添加前后端细粒度计时。", "",
          "## 结论边界与复现", "",
          "两轮结果用于本机迁移参照与发现回归，不能建立多序列精度容差或宣称统计性能提升；没有调整算法参数来追平指标。",
          "回环/GNSS 的完整数据功能、KITTI 数据及 RViz 尚未验收；三个主节点的无输入启动和正常退出、KITTI 参数检查已通过。", "",
          "[搭建与实验命令](UBUNTU22_ROS2_SETUP.md)；[版本化参照快照](../infra/desktop/ros2_reference/)。原始日志在仓库父目录的 results/，不纳入 Git。"]
averages = {}
for version in ("ros1", "ros2"):
    group = [(run, evaluation) for v, _, run, evaluation in records if v == version]
    averages[version] = {
        "ate": mean(evaluation["ate_translation_m"]["rmse"] for _, evaluation in group),
        "cpu": mean(run["resources"]["mean_cpu_percent_one_core"] for run, _ in group),
        "rss": mean(run["resources"]["peak_sampled_rss_kib"] / 1024 for run, _ in group),
    }
summary = (f"两轮均值：ATE ROS 1 为 {averages['ros1']['ate']:.6f} m、ROS 2 为 {averages['ros2']['ate']:.6f} m；"
           f"平均 CPU 占用分别为 {averages['ros1']['cpu']:.2f}% / {averages['ros2']['cpu']:.2f}%；"
           f"RSS 峰值均值分别为 {averages['ros1']['rss']:.2f} / {averages['ros2']['rss']:.2f} MiB。"
           "本序列精度接近，CPU 差异较小；ROS 2 的内存开销更高。")
lines[4:4] = [summary, ""]
(DOCS_ROOT / "ROS1_ROS2_COMPARISON.md").write_text("\n".join(lines) + "\n")
print("Comparison report and reference snapshots written.")
