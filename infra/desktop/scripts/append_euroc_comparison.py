"""Append a versioned experiment section without rewriting prior comparison results."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
from statistics import mean

from workspace_paths import DESKTOP_ROOT, DOCS_ROOT


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--section", required=True, help="Unique section/snapshot identifier")
    parser.add_argument("--title", required=True)
    parser.add_argument("--evidence", action="append", default=[])
    parser.add_argument("runs", nargs="+", type=Path)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.section):
        parser.error("section must be a simple identifier")
    report = DOCS_ROOT / "ROS1_ROS2_COMPARISON.md"
    original = report.read_text()
    marker = f"<!-- experiment:{args.section} -->"
    if marker in original:
        raise RuntimeError("This experiment section is already recorded")
    records, configs = [], {}
    for source in args.runs:
        run = json.loads((source / "run.json").read_text())
        evaluation = json.loads((source / "evaluation.json").read_text())
        if not run["success"] or run.get("vins_exit_code") != 0 or run["playback_exit_code"] != 0:
            raise RuntimeError(f"Incomplete experiment: {source}")
        log = (source / "vins.log").read_text()
        if "failure detection" in log or "throw img" in log:
            raise RuntimeError(f"Failure/dropped pairing: {source}")
        config_file = run.get("config_file", "euroc_stereo_imu_config.yaml")
        config = re.sub(r'^(output_path|pose_graph_save_path):.*$', '',
                        (source / config_file).read_text(), flags=re.M)
        if configs.setdefault(run["mode"], config) != config:
            raise RuntimeError("Configurations differ within a sensor mode")
        records.append((source, run, evaluation))
    snapshot = DESKTOP_ROOT / "comparison_reference" / args.section
    snapshot.mkdir(parents=True, exist_ok=False)
    lines = ["", marker, f"## {args.title}", "",
             "本节追加记录后续版本；此前结果与参照快照保留。原生依赖、算法参数和标定未升级。",
             "使用 MH_01_easy 完整 1 倍速回放；未运行回环/GNSS/RViz。", "",
             "| 实验 | 模式 / 部署 | RMW | 入口 | poses | ATE RMSE (m) | RPE RMSE (m) | CPU (%) | RSS 峰值 (MiB) |",
             "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |"]
    for source, run, evaluation in records:
        destination = snapshot / source.name
        destination.mkdir()
        for filename in ("run.json", "evaluation.json", "vio.csv", "trajectory.tum", "trajectory.png",
                         run["config_file"], "cam0_mei.yaml", "cam1_mei.yaml", "resource_samples.csv"):
            shutil.copy2(source / filename, destination / filename)
        pointer_lines = [line for line in (source / "vins.log").read_text().splitlines()
                         if any(key in line for key in ("image_source ", "image_receive ", "image_view ", "image_ingress ", "sensor_counts ", "replay_counts "))]
        (destination / "ingress_evidence.log").write_text("\n".join(pointer_lines) + "\n")
        resource = run["resources"]
        lines.append(f"| {source.name} | {run['mode']} / {run['deployment']} | {run['rmw'].removeprefix('rmw_')} | "
                     f"{run['image_mode']} | {run['trajectory_poses']} | {evaluation['ate_translation_m']['rmse']:.6f} | "
                     f"{evaluation['rpe_translation_m_one_pose_step']['rmse']:.6f} | {resource['mean_cpu_percent_one_core']:.2f} | "
                     f"{resource['peak_sampled_rss_kib']/1024:.2f} |")
    lines += ["", "copy 保留原入口的 toCvCopy + clone；share 在原生 mono8/8UC1 输入上共享只读视图并持有消息 owner。",
              "前端保存 prev_img 时，同步线程保留上一左图 owner，直到下一次跟踪返回才替换。颜色转换或字节序不匹配时允许有复制。", "",
              "| 实验 | 左 / 右 / IMU / 处理图像 | 共享图像 | 入口物化次数 | 入口物化数据 (MiB) |",
              "| --- | --- | ---: | ---: | ---: |"]
    for source, run, _ in records:
        counts = run["sensor_counts"]
        ingress = run["image_ingress"]
        lines.append(f"| {source.name} | {counts['img0']} / {counts['img1']} / {counts['imu']} / {counts['processed']} | "
                     f"{ingress['shared']} | {ingress['materializations']} | {ingress['bytes']/2**20:.2f} |")
    lines += ["", "以上物化统计只覆盖图像入口显式复制/转换，不是全程序复制计数；颜色转换计为物化。未计入 OpenCV 金字塔、跟踪图、回环、DDS 或磁盘读包内部的复制。", "",
              "同模式、同部署、同 RMW 的重复实验才做 A/B。不同传感器模式不能直接比较精度；不同资源采样范围不能直接比较 CPU/RSS。", ""]
    groups = {}
    for _, run, evaluation in records:
        key = (run["mode"], run["deployment"], run["rmw"])
        groups.setdefault(key, {}).setdefault(run["image_mode"], []).append((run, evaluation))
    for key, variants in groups.items():
        if not all(v in variants for v in ("copy", "share")):
            continue
        values = {}
        for variant, rows in variants.items():
            values[variant] = (mean(r["resources"]["mean_cpu_percent_one_core"] for r, _ in rows),
                               mean(r["resources"]["peak_sampled_rss_kib"]/1024 for r, _ in rows))
        lines.append(f"{key[0]} / {key[1]} / {key[2]}：copy/share 轮数 {len(variants['copy'])}/{len(variants['share'])}，"
                     f"CPU 均值 {values['copy'][0]:.2f}% / {values['share'][0]:.2f}%，"
                     f"RSS 峰值均值 {values['copy'][1]:.2f} / {values['share'][1]:.2f} MiB。")
    lines += ["", "standalone 采样 VINS 进程；component 采样容器 + VINS；composed 采样容器 + VINS + C++ EuRoC 数据源。",
              "composed 的数据源先反序列化 bag，再移动 typed 消息到 VINS，保留记录/头时间戳；每条传感器记录发布 /clock，外部播放器参照为 100 Hz /clock。",
              "composed 改变数据源、RMW 及资源范围，不能用它与旧节点表直接计算组件化加速比。", ""]
    for source, run, _ in records:
        if "image_pointer_checks" in run:
            checks = run["image_pointer_checks"]
            lines.append(f"{source.name}：{len(checks)} 组起始图像指针核验通过，数据源与订阅端的消息/像素地址一致；"
                         f"入口视图{'共享' if run['image_mode']=='share' else '复制'}像素符合所选路径。全序列共享数量另见上表。")
    lines += ["", "各轮干净退出、末帧覆盖和传感器计数已由 runner 检查；ATE/RPE 仍使用相同 evo、SE(3) 无尺度对齐与 0.01 s 匹配容差。",
              "少量重复只用于发现回归；WSL 宿主调度与求解器时间预算仍会造成波动，不能宣称统计显著加速。", "",
              "本轮未实施跨进程共享内存、相机 DMA-BUF、RGA、NEON 或全程序零拷贝；未测 DDR 带宽和功耗。", "",
              f"[本节参照快照](../infra/desktop/comparison_reference/{args.section}/)。源码/二进制哈希、RMW、资源口径及原始采样见各轮 run.json / resource_samples.csv。"]
    for evidence in args.evidence:
        source = Path(evidence)
        shutil.copy2(source, snapshot / source.name)
    manifest = [f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(DESKTOP_ROOT)}"
                for p in sorted(snapshot.rglob('*')) if p.is_file()]
    (snapshot / "SHA256SUMS").write_text("\n".join(manifest) + "\n")
    report.write_text(original + "\n".join(lines) + "\n")
    assert report.read_text().startswith(original)
    print(f"Appended {len(records)} experiments; prior report retained.")


if __name__ == "__main__":
    main()
