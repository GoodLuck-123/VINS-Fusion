"""Serial milestone trials using current ROS 2 code; no model calls between trials."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import re
import time

from workspace_paths import REPO_ROOT as REPO, WORKSPACE_ROOT as WORKSPACE
SCRIPTS = REPO / 'infra/desktop/scripts'
PRESETS = {
    'baseline': [('stereo_imu', 'standalone', 'copy', 'ros', False)] * 2,
    'components': [('stereo_imu', 'standalone', v, 'ros', False) for v in ('copy', 'share', 'share', 'copy')]
                  + [('mono_imu', 'standalone', v, 'ros', False) for v in ('copy', 'share')]
                  + [('stereo_imu', 'composed', v, 'ros', False) for v in ('copy', 'share')],
    'pmu': [('stereo_imu', 'standalone', v, 'ros', True) for v in ('copy', 'share')],
    'shared': [(m, 'split', 'share', t, False) for m in ('stereo_imu', 'mono_imu') for t in ('ros', 'memfd')],
    'vgem': [(m, 'split', 'share', 'vgem', False) for m in ('stereo_imu', 'mono_imu')],
}


def freeze(extra_paths=()):
    paths = subprocess.check_output(['git', 'ls-files', '-z', 'camera_models', 'vins_estimator',
            'loop_fusion', 'global_fusion', 'ros2', 'config/euroc', 'infra/desktop/scripts', 'infra/desktop/uv.lock'],
            cwd=REPO).decode().split('\0')
    files = [REPO / p for p in paths if p] + [Path(__file__).resolve()]
    files += list(extra_paths)
    files += list((WORKSPACE / '.infra/ros2_ws/install/lib').rglob('*.so'))
    files += [WORKSPACE / '.infra/ros2_ws/install/lib/vins/vins_node',
              WORKSPACE / '.infra/ros2_ws/install/lib/vins/euroc_player_node']
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(files))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=PRESETS, required=True)
    parser.add_argument('--prefix', required=True)
    parser.add_argument('--dds-profile', type=Path)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_-]+', args.prefix):
        parser.error('Use a simple result prefix without path separators')
    profile_paths = [args.dds_profile.resolve()] if args.dds_profile else []
    if profile_paths and not profile_paths[0].is_file():
        parser.error('DDS profile must be an existing file')
    trials = []
    for i, (mode, deployment, image_mode, transport, pmu) in enumerate(PRESETS[args.phase], 1):
        trials.append(dict(name=f'{args.prefix}_{mode.split("_")[0]}_{deployment}_{image_mode}_{transport}_{i:02d}',
                           mode=mode, deployment=deployment, image_mode=image_mode, transport=transport, pmu=pmu))
    if args.dry_run:
        print(json.dumps(trials, indent=2)); return
    from run_shared_repeats import assert_quiet, execute
    assert_quiet()
    directory = WORKSPACE / 'results/ubuntu22-reproduction' / args.prefix
    directory.mkdir(exist_ok=False)
    state = dict(status='running', trials=trials, completed=[], frozen_files=freeze(profile_paths))
    env = os.environ.copy()
    evaluation_env = env.copy()
    evaluation_env['UV_CACHE_DIR'] = str(WORKSPACE / '.infra/uv-cache')
    source_env = 'set -e\nsource ' + shlex.quote(str(SCRIPTS / 'ros2_env.sh')) + '\nexec '
    try:
        for trial in trials:
            assert_quiet()
            if freeze(profile_paths) != state['frozen_files']:
                raise RuntimeError('Source or native binaries changed during the phase')
            state['current'] = trial
            (directory / 'state.json').write_text(json.dumps(state, indent=2) + '\n')
            env['VINS_RMW_IMPLEMENTATION'] = ('rmw_cyclonedds_cpp' if trial['deployment'] in ('split', 'composed')
                                               else 'rmw_fastrtps_cpp')
            env.pop('CYCLONEDDS_URI', None)
            if args.dds_profile and trial['deployment'] == 'split':
                env['CYCLONEDDS_URI'] = 'file://' + str(args.dds_profile.resolve())
            command = ['python', str(SCRIPTS / 'run_ros2_euroc.py'), '--name', trial['name'],
                       '--mode', trial['mode'], '--deployment', trial['deployment'], '--image-mode', trial['image_mode'],
                       '--image-transport', trial['transport']]
            if trial['pmu']:
                command += ['--perf-counters']
            execute(['bash', '-c', source_env + shlex.join(command)],
                    directory / (trial['name'] + '.log'), env, 450)
            assert_quiet()
            output = WORKSPACE / 'results/ros2' / trial['name']
            execute(['uv', 'run', '--offline', '--project', str(REPO / 'infra/desktop'), '--locked',
                     'python', str(SCRIPTS / 'evaluate_baseline.py'), str(output), '--label', trial['name']],
                    directory / (trial['name'] + '-evaluation.log'), evaluation_env, 90)
            run = json.loads((output / 'run.json').read_text())
            if not run['success'] or run['vins_exit_code'] or run['playback_exit_code']:
                raise RuntimeError('Playback or shutdown failed')
            expected = dict(img0=3682, img1=3682 if trial['mode'] == 'stereo_imu' else 0, imu=36820, processed=3682)
            if run['sensor_counts'] != expected:
                raise RuntimeError('Incomplete sensor counts')
            log = (output / 'vins.log').read_text()
            if 'failure detection' in log or 'throw img' in log:
                raise RuntimeError('Tracking reset or pairing drop')
            if trial['deployment'] == 'split' and not run['pixel_timestamp_sha256']['source_matches_consumer']:
                raise RuntimeError('Pixel/timestamp signatures differ')
            if trial['transport'] != 'ros':
                w, r = run['shared_writer'], run['shared_reader']
                if w['outstanding'] or w['failed'] or r['failed']:
                    raise RuntimeError('Unreturned slot or shared-buffer error')
            if trial['pmu'] and run['cpu_perf_counters']['errors']:
                raise RuntimeError('PMU counter unavailable')
            state['completed'].append(str(output))
            if freeze(profile_paths) != state['frozen_files']:
                raise RuntimeError('Source or native binaries changed during replay')
            (directory / 'state.json').write_text(json.dumps(state, indent=2) + '\n')
            time.sleep(10)
        state['status'] = 'complete'
    except BaseException as error:
        state.update(status='failed', failure=f'{type(error).__name__}: {error}')
        raise
    finally:
        (directory / 'state.json').write_text(json.dumps(state, indent=2) + '\n')


if __name__ == '__main__':
    main()
