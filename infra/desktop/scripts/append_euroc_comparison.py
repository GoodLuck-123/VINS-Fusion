"""Append a versioned experiment section without rewriting prior comparison results."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
from statistics import mean

from workspace_paths import DESKTOP_ROOT, DOCS_ROOT
from markdown_docs import format_prose


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--section", required=True, help="Unique section/snapshot identifier")
    parser.add_argument("--title", required=True)
    parser.add_argument("--evidence", action="append", default=[])
    parser.add_argument("runs", nargs="+", type=Path)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.section):
        parser.error("section must be a simple identifier")
    report = DOCS_ROOT / "05_EUROC_ROS1_ROS2_COMPARISON.md"
    original = report.read_text()
    marker = f"<!-- experiment:{args.section} -->"
    if marker in original:
        raise RuntimeError("This experiment section is already recorded")
    records, configs, digests = [], {}, {}
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
        if run.get("deployment") == "split":
            signature = run["pixel_timestamp_sha256"]
            if not signature["source_matches_consumer"] or digests.setdefault(run["mode"], signature) != signature:
                raise RuntimeError("Pixel/timestamp signatures differ within a sensor mode")
        records.append((source, run, evaluation))
    snapshot = DESKTOP_ROOT / "comparison_reference" / args.section
    snapshot.mkdir(parents=True, exist_ok=False)
    lines = ["", marker, f"## {args.title}", "",
             "本节追加记录后续版本；此前结果与参照快照保留。原生依赖、算法参数和标定未升级。",
             "使用 MH_01_easy 完整回放，目标供给倍率为 1；背压可能延长实际墙钟时间，不能以配置倍率证明实时性。未运行回环/GNSS/RViz。", "",
             "| 实验 | 模式 / 部署 | RMW | 传输 / 入口 | poses | ATE RMSE (m) | RPE RMSE (m) | CPU (%) | RSS 峰值 (MiB) |",
             "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |"]
    for source, run, evaluation in records:
        destination = snapshot / source.name
        destination.mkdir()
        for filename in ("run.json", "evaluation.json", "vio.csv", "trajectory.tum", "trajectory.png",
                         run["config_file"], "cam0_mei.yaml", "cam1_mei.yaml", "resource_samples.csv"):
            shutil.copy2(source / filename, destination / filename)
        if (source / "cyclonedds.xml").exists(): shutil.copy2(source / "cyclonedds.xml", destination / "cyclonedds.xml")
        if (source / "source_resource_samples.csv").exists(): shutil.copy2(source / "source_resource_samples.csv", destination / "source_resource_samples.csv")
        logs=(source / "vins.log").read_text()
        if (source / "playback.log").exists(): logs += "\n"+(source / "playback.log").read_text()
        pointer_lines = [line for line in logs.splitlines()
                         if any(key in line for key in ("image_source ", "image_receive ", "image_view ", "image_ingress ", "sensor_counts ", "replay_counts ", "shared_peer ", "shared_buffer ", "shared_writer ", "shared_reader ", "image_digest "))]
        (destination / "ingress_evidence.log").write_text("\n".join(pointer_lines) + "\n")
        resource = run["resources"]
        lines.append(f"| {source.name} | {run['mode']} / {run['deployment']} | {run['rmw'].removeprefix('rmw_')} | "
                     f"{run.get('image_transport','ros')} / {run['image_mode']} | {run['trajectory_poses']} | {evaluation['ate_translation_m']['rmse']:.6f} | "
                     f"{evaluation['rpe_translation_m_one_pose_step']['rmse']:.6f} | {resource['mean_cpu_percent_one_core']:.2f} | "
                     f"{resource['peak_sampled_rss_kib']/1024:.2f} |")
    shared_phase=any(run.get("deployment")=="split" for _,run,_ in records)
    if shared_phase:
        lines += ["", "本节 split 每轮均运行两个独立原生进程：同一个 typed EuRoC 数据源 + VINS。ROS 对照也启用全像素 SHA256，使用相同时间戳、数据源、Cyclone DDS 和线程/算法配置。",
                  "上表 CPU/RSS 为 VINS 单进程；下表包含数据源，CPU 之和以共同观测墙钟归一。SHA256 每张图像在数据源、消费端各计算一次，CPU 数值包含校验成本。",
                  "三条路径使用相同的进程级 cyclonedds_wsl.xml（1400 B 数据报上限、1024 B 分片）；WSL 镜像网络的大包故障诊断单独归档。小分片会增加 DDS 开销，不能把本机省去 DDS 图像路径的 CPU 收益外推为 ARM/DDR/功耗提升。",
                  "共享路径消费端校验在线程接收处，ROS 对照校验在同步入口，因此调度与执行阶段仍有差异。PSS 较适合共享页比较；各进程独立采样峰值之和不是同时峰值，也不是 DDR 用量。", "",
                  "| 实验 | 数据源 CPU 秒 | 两进程 CPU 秒 | 两进程平均 CPU (%) | VINS / 数据源 PSS 峰值 (MiB) | 逐帧校验 | 数据源显式像素复制 (MiB) |",
                  "| --- | ---: | ---: | ---: | --- | --- | ---: |"]
        for source,run,_ in records:
            if run.get("deployment")!="split": continue
            r=run["resources"]; sr=run["source_resources"]
            copied=run.get("shared_writer",{}).get("source_bytes")
            lines.append(f"| {source.name} | {sr['cpu_time_s']:.2f} | {run['combined_cpu_time_s']:.2f} | {run['combined_mean_cpu_percent_one_core']:.2f} | "
                         f"{r.get('peak_sampled_pss_kib',0)/1024:.2f} / {sr.get('peak_sampled_pss_kib',0)/1024:.2f} | 全帧通过 | "
                         + (f"{copied/2**20:.2f}" if copied is not None else "未统计 DDS 内部复制")+" |")
        lines += ["", "每摄像头累计 SHA256 包括每帧原始 header 时间戳和逐行有效像素摘要，忽略行尾填充；数据源与消费端一致，且同模式的三种传输应一致。",
                  "memfd 是普通共享像素；vgem 为内核 DRM 导出的真实 DMA-BUF。通过 SCM_RIGHTS 传递内核句柄，在独立 PID 内导入并核验 device/inode/长度，消费端只读 mmap；不传裸指针或 fd 数字。",
                  "32 个有界槽位记录代次，缓冲用完会阻塞；归还发生在当前与上一左帧 owner 全部释放之后。DMA-BUF CPU 读写各有 START/END 同步，无硬件 DMA/fence/RGA 参与本次回放。",
                  "bag 反序列化仍分配图像；共享数据源每帧仍复制一次到池中。此次消除的是跨进程图像消息的序列化/像素搬运路径及 VINS 入口复制，不是全链路零拷贝，也没有完整统计 DDS 内部复制次数。"]
    if shared_phase:
        lines += ["", "| 实验 | 回放墙钟 (s) | 后端稳定等待 (s) |",
                  "| --- | ---: | ---: |"]
        for source,run,_ in records:
            lines.append(f"| {source.name} | {run['playback_wall_s']:.2f} | {run['settling_wait_s']:.2f} |")
        lines += ["", "回放墙钟含启动就绪、3 秒预延迟和完成通知观察；同来源对照可比较额外阻塞，不能直接等同于传感器记录时长。稳定等待含统一至少约 6 秒的观测条件。"]
    if shared_phase:
        shared_records=[(source,run) for source,run,_ in records if "shared_writer" in run]
        if shared_records:
            lines += ["", "| 实验 | 池复用次数 | 池满等待次数 | 退出未归还槽位 | 源端 / 消费端错误 | 独立进程句柄核验 |",
                      "| --- | ---: | ---: | ---: | --- | --- |"]
            for source,run in shared_records:
                w=run["shared_writer"]; r=run["shared_reader"]
                lines.append(f"| {source.name} | {w['reuses']} | {w['waits']} | {w['outstanding']} | {w['failed']} / {r['failed']} | 通过 |")
            lines += ["", "池为每轮重新创建，停止后关闭 fd、解除映射、删除本轮 socket；源码及本地 ASan 压力证据补充生命周期核验，未进行长时间故障恢复验收。"]
    if any("cpu_perf_counters" in run for _, run, _ in records):
        lines += ["", "| 实验 | cycles (十亿) | instructions (十亿) | cache misses (百万) | IPC | misses / 千条指令 |",
                  "| --- | ---: | ---: | ---: | ---: | ---: |"]
        for source, run, _ in records:
            events = run.get("cpu_perf_counters", {}).get("events", {})
            values = []
            for name, divisor in (("cpu_cycles", 1e9), ("instructions", 1e9), ("cache_misses", 1e6)):
                event = events.get(name, {})
                values.append(f"{event['count']/divisor:.3f}" if event.get("running_fraction") == 1.0 else "—")
            if all(events.get(n, {}).get("running_fraction") == 1.0 for n in ("cpu_cycles", "instructions", "cache_misses")) and events["cpu_cycles"]["count"] and events["instructions"]["count"]:
                ipc = events["instructions"]["count"] / events["cpu_cycles"]["count"]
                mpki = 1000 * events["cache_misses"]["count"] / events["instructions"]["count"]
                values += [f"{ipc:.3f}", f"{mpki:.3f}"]
            else:
                values += ["—", "—"]
            lines.append(f"| {source.name} | " + " | ".join(values) + " |")
        lines += ["", "CPU PMU 统计用户态及继承的工作线程，含启动/退出及短暂门控；与 subscription-ready-to-drain 的资源采样窗口不同。",
                  "表中仅显示无计数器轮换的事件；原始 time_enabled/time_running 和错误保存在 run.json。",
                  "WSL 虚拟化 PMU 的 IPC/cache misses 仅用于诊断，不是 DDR 流量、memory-bound 判定或功耗实测。"]
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
        lines.append("")
    lines += ["", "standalone 采样 VINS 进程；component 采样容器 + VINS；composed 采样容器 + VINS + C++ EuRoC 数据源。",
              "composed 的数据源先反序列化 bag，再移动 typed 消息到 VINS，保留记录/头时间戳；每条传感器记录发布 /clock，外部播放器参照为 100 Hz /clock。",
              "composed 改变数据源、RMW 及资源范围，不能用它与旧节点表直接计算组件化加速比。", ""]
    for source, run, _ in records:
        if "image_pointer_checks" in run:
            checks = run["image_pointer_checks"]
            lines.append(f"{source.name}：{len(checks)} 组起始图像指针核验通过，数据源与订阅端的消息/像素地址一致；"
                         f"入口视图{'共享' if run['image_mode']=='share' else '复制'}像素符合所选路径。全序列共享数量另见上表。")
            lines.append("")
    lines += ["", "各轮干净退出、末帧覆盖和传感器计数已由 runner 检查；ATE/RPE 仍使用相同 evo、SE(3) 无尺度对齐与 0.01 s 匹配容差。",
              "少量重复只用于发现回归；WSL 宿主调度与求解器时间预算仍会造成波动，不能宣称统计显著加速。", "",
              ("本轮实现 EuRoC 跨进程共享像素与可选 VGEM DMA-BUF；相机 DMA、RGA、NEON、全程序零拷贝未实施，DDR 带宽和功耗未实测。" if shared_phase else "本轮未实施跨进程共享内存、相机 DMA-BUF、RGA、NEON 或全程序零拷贝；未测 DDR 带宽和功耗。"), "",
              f"[本节参照快照](../infra/desktop/comparison_reference/{args.section}/)。源码/二进制哈希、RMW、资源口径及原始采样见各轮 run.json / resource_samples.csv。"]
    for evidence in args.evidence:
        source = Path(evidence)
        shutil.copy2(source, snapshot / source.name)
    manifest = [f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(DESKTOP_ROOT)}"
                for p in sorted(snapshot.rglob('*')) if p.is_file()]
    (snapshot / "SHA256SUMS").write_text("\n".join(manifest) + "\n")
    report.write_text(original + format_prose("\n".join(lines) + "\n"))
    assert report.read_text().startswith(original)
    print(f"Appended {len(records)} experiments; prior report retained.")


if __name__ == "__main__":
    main()
