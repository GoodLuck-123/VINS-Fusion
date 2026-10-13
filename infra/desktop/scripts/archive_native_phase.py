"""Archive new native-host evidence and append readable results without touching frozen WSL data."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil

from workspace_paths import DESKTOP_ROOT, DOCS_ROOT, WORKSPACE_ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', required=True)
    parser.add_argument('--title', required=True)
    parser.add_argument('runs', nargs='+', type=Path)
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_-]+', args.phase):
        parser.error('Use a simple phase identifier')
    records = []
    for directory in args.runs:
        run = json.loads((directory / 'run.json').read_text())
        evaluation = json.loads((directory / 'evaluation.json').read_text())
        if not run['success'] or run['playback_exit_code'] != 0:
            raise RuntimeError(f'Incomplete playback: {directory}')
        expected_exit = -6 if directory.parent.name == 'ros1' else 0
        if run['vins_exit_code'] != expected_exit:
            raise RuntimeError(f'Unexpected shutdown: {directory}')
        log = (directory / 'vins.log').read_text()
        if 'failure detection' in log or 'throw img' in log:
            raise RuntimeError(f'Tracking reset or pair drop: {directory}')
        if evaluation['matched_estimate_fraction'] < 0.95:
            raise RuntimeError(f'Insufficient reference matching: {directory}')
        records.append((directory, run, evaluation))
    report = DOCS_ROOT / '05_EUROC_ROS1_ROS2_COMPARISON.md'
    original = report.read_text() if report.exists() else (
        '# 原生 Ubuntu 22.04 EuRoC 复现实测\n\n'
        '本页只记录当前物理主机实测。WSL 原报告保存在历史 tag；历史归档及冻结哈希保持原样\n\n'
        '主机：Ubuntu 22.04.5、Linux 6.8.0-138-generic、AMD Ryzen 7 9800X3D，16 逻辑 CPU、约 30 GiB 内存\n\n'
        '输入为相同 SHA256 的 MH_01_easy；OpenCV 4.2.0、Ceres 1.14.0、标定及算法参数保持原版。'
        'evo 使用 IMU/body 真值、SE(3) 对齐、不校正尺度，相邻位姿 RPE 约 0.1 秒间隔\n\n'
        'DDR 流量不可用；CPU 能量节点默认不可读。GPU hwmon 功率不代表 CPU VIO 功耗\n')
    marker = f'<!-- native-phase:{args.phase} -->'
    if marker in original:
        raise RuntimeError('Phase already recorded')
    snapshot = DESKTOP_ROOT / 'comparison_reference' / 'native_ubuntu22_20261013' / args.phase
    if snapshot.exists():
        raise RuntimeError('Preserve existing evidence; use a new phase identifier')
    snapshot.mkdir(parents=True)
    lines = ['', marker, f'## {args.title}', '',
             '| 实验 | 模式 / 部署 / 入口 | poses / 匹配 | ATE RMSE (m) | RPE RMSE (m) | 回放 / 排空 (s) | VINS 退出 |',
             '| --- | --- | ---: | ---: | ---: | --- | ---: |']
    resources = ['', 'CPU 秒为各进程全部线程累计值；RSS/PSS 是各进程独立采样峰值，不能相加当作同时峰值。回放、排空分别列出，完整处理不等于实时验收\n',
                 '| 实验 | VINS CPU (s) | 源端 CPU (s) | 合计 CPU (s) | VINS RSS / PSS (MiB) | 源端 RSS / PSS (MiB) |',
                 '| --- | ---: | ---: | ---: | --- | --- |']
    for directory, run, evaluation in records:
        mode = run.get('mode', 'stereo_imu_vio')
        deployment = run.get('deployment', 'ROS 1 standalone')
        ingress = run.get('image_transport', 'ros') + '/' + run.get('image_mode', 'copy')
        drain = run.get('post_playback_drain_s', run.get('settling_wait_s'))
        drain_text = f'{drain:.2f}' if drain is not None else '未记录'
        lines.append(f"| {directory.name} | {mode} / {deployment} / {ingress} | "
                     f"{run['trajectory_poses']} / {evaluation['matched_poses']} | "
                     f"{evaluation['ate_translation_m']['rmse']:.6f} | "
                     f"{evaluation['rpe_translation_m_one_pose_step']['rmse']:.6f} | "
                     f"{run['playback_wall_s']:.2f} / {drain_text} | {run['vins_exit_code']} |")
        r = run['resources']
        s = run.get('source_resources')
        memory = lambda x: f"{x['peak_sampled_rss_kib']/1024:.2f} / {x['peak_sampled_pss_kib']/1024:.2f}"
        source_cpu = f"{s['cpu_time_s']:.2f}" if s else '未采样'
        total = f"{run['combined_cpu_time_s']:.2f}" if s else '仅 VINS'
        resources.append(f"| {directory.name} | {r['cpu_time_s']:.2f} | {source_cpu} | {total} | "
                         f"{memory(r)} | {memory(s) if s else '未采样'} |")
        destination = snapshot / directory.name
        destination.mkdir()
        for path in directory.iterdir():
            if path.name in ('run.json', 'evaluation.json', 'validation.json', 'vio.csv', 'trajectory.tum',
                             'trajectory.png', 'resource_samples.csv', 'resource_details.csv',
                             'source_resource_samples.csv', 'cyclonedds.xml') or path.suffix == '.yaml':
                shutil.copy2(path, destination / path.name)
        logs = (directory / 'vins.log').read_text()
        if (directory / 'playback.log').exists():
            logs += '\n' + (directory / 'playback.log').read_text()
        evidence = [line for line in logs.splitlines() if any(key in line.lower() for key in
                    ('initialization', 'failure detection', 'throw img', 'image_ingress ', 'sensor_counts ',
                     'replay_counts ', 'shared_peer ', 'shared_buffer ', 'shared_writer ', 'shared_reader ',
                     'image_digest ', 'image_source ', 'image_receive ', 'image_view '))]
        (destination / 'runtime_evidence.log').write_text('\n'.join(evidence) + '\n')
    host = WORKSPACE_ROOT / 'results/ubuntu22-reproduction'
    for name in ('host.json', 'hardware-capabilities.json', 'hardware-capabilities-enabled.json', 'vgem-device.json'):
        if (host / name).exists():
            shutil.copy2(host / name, snapshot / name)
    manifest = [f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(snapshot)}'
                for p in sorted(snapshot.rglob('*')) if p.is_file()]
    (snapshot / 'SHA256SUMS').write_text('\n'.join(manifest) + '\n')
    lines += resources + ['', f'[本阶段证据](../infra/desktop/comparison_reference/native_ubuntu22_20261013/{args.phase}/)', '']
    report.write_text(original + '\n'.join(lines))
    print(snapshot)


if __name__ == '__main__':
    main()
