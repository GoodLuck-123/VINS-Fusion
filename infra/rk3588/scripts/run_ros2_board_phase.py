"""Upload data optionally, run a serial board phase, and collect logs with vins-remote."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

REPO = Path(__file__).resolve().parents[3]
WORKSPACE = REPO.parent
# Desktop duplicates are removed. Baseline stereo/copy is reused by components.
PRESETS = {
    'baseline': [('stereo_imu', 'standalone', 'copy', 'ros', False)],
    'components': [('stereo_imu', 'standalone', 'share', 'ros', False),
                   ('mono_imu', 'standalone', 'copy', 'ros', False),
                   ('mono_imu', 'standalone', 'share', 'ros', False),
                   ('stereo_imu', 'composed', 'copy', 'ros', False),
                   ('stereo_imu', 'composed', 'share', 'ros', False)],
    'pmu': [('stereo_imu', 'standalone', image, 'ros', True) for image in ['copy', 'share']],
    'shared': [(mode, 'split', 'share', transport, False)
               for mode in ['stereo_imu', 'mono_imu'] for transport in ['ros', 'memfd']],
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', default='firefly@10.106.0.220')
    parser.add_argument('--runtime', required=True, help='Previously verified remote runtime directory')
    parser.add_argument('--ros-addon', help='Previously verified remote Fast DDS addon directory')
    parser.add_argument('--prefix', required=True, help='Unique result prefix; never overwrite a failed trial')
    parser.add_argument('--data-parent', default='vins-workspace/datasets/euroc_20261014')
    parser.add_argument('--upload-data', action='store_true')
    parser.add_argument('--phase', choices=PRESETS, required=True)
    parser.add_argument('--directory', type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_-]+', args.prefix):
        parser.error('Use a simple unique prefix without path separators')
    directory = args.directory.resolve()
    directory.mkdir(parents=True, exist_ok=False)
    payload = directory / 'drivers'
    payload.mkdir()
    bag = WORKSPACE / 'data/euroc/MH_01_easy_ros2'
    data_hashes = {}
    for path in sorted(bag.rglob('*')):
        if path.is_file():
            digest = hashlib.sha256()
            with path.open('rb') as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                    digest.update(chunk)
            data_hashes[str(path.relative_to(bag))] = digest.hexdigest()
    trials = [dict(name=f'{args.prefix}_{mode}_{deployment}_{image}_{transport}_{index}',
                   mode=mode, deployment=deployment, image=image, transport=transport, pmu=pmu,
                   rmw='rmw_cyclonedds_cpp' if deployment in ['composed', 'split'] else 'rmw_fastrtps_cpp')
              for index, (mode, deployment, image, transport, pmu) in enumerate(PRESETS[args.phase], 1)]
    plan = dict(runtime=args.runtime, bag=f'{args.data_parent}/{bag.name}',
                bag_hashes=data_hashes, trials=trials,
                runtime_manifest_sha256=hashlib.sha256((REPO / 'infra/rk3588/reference/runtime_20261014/payload_files.json').read_bytes()).hexdigest(),
                driver_commit=subprocess.check_output(['git', '-C', str(REPO), 'rev-parse', 'HEAD'], text=True).strip())
    if args.ros_addon:
        plan['ros_addon'] = args.ros_addon
        plan['addon_manifest_sha256'] = hashlib.sha256((WORKSPACE / '.infra/rk3588/fastrtps-payload/files.json').read_bytes()).hexdigest()
    (payload / 'plan.json').write_text(json.dumps(plan, indent=2) + '\n')
    shutil.copy2(WORKSPACE / 'results/ros2/bag_conversion.json', payload / 'bag_conversion.json')
    shutil.copy2(Path(__file__).parent / 'run_board_trials.py', payload / 'run_board_trials.py')
    tool = str(WORKSPACE / '.infra/bin/vins-remote')
    if args.upload_data:
        subprocess.run([tool, args.target, str(bag), '--dest', args.data_parent], check=True)
    subprocess.run([tool, args.target, str(payload), '--run',
                    str(Path(__file__).parent / 'ros2_board_phase.sh'),
                    '--output', str(directory / 'board'), '--timeout', '7200'], check=True)
    # Evaluation stays on the host in the same locked environment as desktop runs.
    evaluation_env = os.environ.copy()
    for key in ['PYTHONPATH', 'LD_LIBRARY_PATH', 'VIRTUAL_ENV', 'CONDA_PREFIX']:
        evaluation_env.pop(key, None)
    evaluation_env['UV_CACHE_DIR'] = str(WORKSPACE / '.infra/uv-cache')
    for trial in trials:
        with (directory / (trial['name'] + '-evaluation.log')).open('w') as log:
            subprocess.run(['uv', 'run', '--offline', '--project', str(REPO / 'infra/desktop'), '--locked',
                            'python', str(REPO / 'infra/desktop/scripts/evaluate_baseline.py'),
                            str(directory / 'board' / trial['name']), '--label', trial['name']],
                           stdout=log, stderr=subprocess.STDOUT, env=evaluation_env, check=True)


if __name__ == '__main__':
    main()
