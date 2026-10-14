"""Verify and freeze a completed board split ROS/shared-buffer phase."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase-directory', type=Path, required=True)
    parser.add_argument('--audit-directory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    phase = args.phase_directory
    board = phase / 'trial/board'
    event = json.loads((phase / 'event.json').read_text())
    plan = json.loads((board / 'plan.json').read_text())
    state = json.loads((board / 'state.json').read_text())
    audit = json.loads((args.audit_directory / 'remote_jobs.json').read_text())
    assert event['status'] == 'complete' and event['exit_code'] == 0
    assert state['status'] == 'complete' and not audit['active_prior_task_processes']
    assert state['completed'] == [t['name'] for t in plan['trials']]
    conversion = json.loads((phase / 'trial/drivers/bag_conversion.json').read_text())['ros2']
    last_image = conversion['/cam0/image_raw']['last_header_ns']
    summaries = []
    by_mode = {}
    for trial in plan['trials']:
        output = board / trial['name']
        run = json.loads((output / 'run.json').read_text())
        evaluation = json.loads((output / 'evaluation.json').read_text())
        stereo = trial['mode'] == 'stereo_imu'
        frames = 7364 if stereo else 3682
        expected = dict(img0=3682, img1=3682 if stereo else 0, imu=36820, processed=3682)
        assert run['success'] and run['sensor_counts'] == expected
        assert run['vins_exit_code'] == run['playback_exit_code'] == run['replay_result_code'] == 0
        assert run['deployment'] == 'split' and run['rmw'] == 'rmw_cyclonedds_cpp'
        assert run['image_transport'] == trial['transport'] and run['image_mode'] == 'share'
        assert abs(run['last_timestamp_ns'] - last_image) <= 512
        assert evaluation['estimated_poses'] == run['trajectory_poses'] == 1831
        assert evaluation['matched_poses'] == 1819 and evaluation['alignment_scale'] == 1
        log = (output / 'vins.log').read_text()
        assert log.count('Initialization finish!') == 1
        assert 'failure detection' not in log and 'throw img' not in log
        assert run['image_ingress']['materializations'] == run['image_ingress']['bytes'] == 0
        assert run['pixel_timestamp_sha256']['source_matches_consumer']
        digest = run['pixel_timestamp_sha256']
        if trial['mode'] in by_mode:
            assert digest == by_mode[trial['mode']]
        by_mode[trial['mode']] = digest
        if trial['transport'] != 'ros':
            writer, reader = run['shared_writer'], run['shared_reader']
            assert writer['backend'] == trial['transport'] and writer['frames'] == frames
            assert writer['outstanding'] == writer['failed'] == 0
            assert reader['frames'] == reader['verified'] == frames and reader['failed'] == 0
            if trial['transport'] == 'dma_heap':
                command = json.loads((board / (trial['name'] + '-driver-command.json')).read_text())
                assert command[command.index('--shared-device') + 1] == trial['shared_device']
        item = dict(name=trial['name'], mode=trial['mode'], transport=trial['transport'],
                    ate_rmse_m=evaluation['ate_translation_m']['rmse'],
                    rpe_rmse_m=evaluation['rpe_translation_m_one_pose_step']['rmse'],
                    combined_cpu_s=run['combined_cpu_time_s'],
                    playback_s=run['playback_wall_s'], drain_s=run['settling_wait_s'],
                    poses=run['trajectory_poses'], matches=evaluation['matched_poses'],
                    sensor_counts=expected, pixel_timestamp_sha256=digest,
                    final_timestamp_error_ns=run['last_timestamp_ns'] - last_image)
        for key in ['resources', 'source_resources']:
            resource = run[key]
            item[key] = dict(cpu_s=resource['cpu_time_s'], rss_mib=resource['peak_sampled_rss_kib']/1024,
                             pss_mib=resource['peak_sampled_pss_kib']/1024)
        if 'shared_writer' in run:
            item['shared_writer'] = run['shared_writer']
            item['shared_reader'] = run['shared_reader']
        summaries.append(item)
    destination = args.output
    destination.mkdir(parents=True, exist_ok=False)
    originals = {}
    sources = [(phase / 'event.json', Path('event.json')), (phase / 'console.log', Path('console.log')),
               (args.audit_directory / 'remote_jobs.json', Path('remote_jobs.json'))]
    sources += [(p, Path('board') / p.relative_to(board)) for p in sorted(board.rglob('*')) if p.is_file()]
    sources += [(p, Path('drivers') / p.relative_to(phase/'trial/drivers'))
                for p in sorted((phase/'trial/drivers').rglob('*')) if p.is_file()]
    for source, relative in sources:
        originals[str(relative)] = hashlib.sha256(source.read_bytes()).hexdigest()
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.suffix in {'.log', '.csv', '.tum', '.jsonl'}:
            with gzip.GzipFile(filename=str(target)+'.gz', mode='wb', mtime=0) as stream:
                stream.write(source.read_bytes())
        else:
            shutil.copy2(source, target)
    summary = dict(trials=summaries, original_file_sha256=originals, ddr='Unavailable', power='Unavailable',
                   scope='VINS and source CPU separately and combined; per-process RSS/PSS; subscription-ready-to-drain')
    (destination/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    (destination/'README.md').write_text('# RK3588 完整共享传输验收\n\n每配置一次、串行回放，完整输入/末帧、一次初始化、无重置/配对丢帧、主机评估及退出通过；像素/时间戳摘要一致，所有共享槽位归还，结束审计无旧作业活进程\n\n分别报告 VINS/源端全线程 CPU 与 RSS/PSS；源端仍复制像素到池，排空后成功不称为实时通过。单轮性能差异不当作稳定收益，DDR/功耗不可用\n\n日志/CSV/TUM/telemetry 以 gzip 保存，summary.json 保留每个原文件 SHA256，SHA256SUMS 校验归档文件。主机事件 UTC 为时间依据，板端墙上时钟偏移保留；固定运行包、addon、bag、DDS 配置及完整方案见 drivers/plan.json 与 board/<trial>/run.json\n')
    (destination/'SHA256SUMS').write_text(''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(destination)}\n'
        for p in sorted(destination.rglob('*')) if p.is_file() and p.name!='SHA256SUMS'))
    print(json.dumps(summaries, indent=2))


if __name__ == '__main__':
    main()
