"""Execute one unchanged-configuration trial per preset, retaining failures and telemetry."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time


def main():
    payload = Path(os.environ['VINS_REMOTE_PAYLOAD'])
    logs = Path(os.environ['VINS_REMOTE_ROOT']) / 'logs'
    runtime = Path(os.environ['VINS_BOARD_RUNTIME'])
    plan = json.loads((payload / 'plan.json').read_text())
    bag = (Path.home() / Path(plan['bag']).expanduser()).resolve()
    manifest_file = runtime / 'files.json'
    if hashlib.sha256(manifest_file.read_bytes()).hexdigest() != plan['runtime_manifest_sha256']:
        raise RuntimeError('Runtime manifest differs from accepted deployment')
    manifest = json.loads(manifest_file.read_text())
    addon = os.environ.get('VINS_BOARD_ROS_ADDON')
    addon_manifest = {}
    if addon:
        addon = Path(addon)
        addon_file = addon / 'files.json'
        if hashlib.sha256(addon_file.read_bytes()).hexdigest() != plan['addon_manifest_sha256']:
            raise RuntimeError('Addon manifest differs from accepted deployment')
        addon_manifest = json.loads(addon_file.read_text())

    def verify_runtime():
        for relative, expected in manifest.items():
            if hashlib.sha256((runtime / relative).read_bytes()).hexdigest() != expected:
                raise RuntimeError(f'Runtime changed: {relative}')
        for relative, expected in addon_manifest.items():
            if hashlib.sha256((addon / relative).read_bytes()).hexdigest() != expected:
                raise RuntimeError(f'ROS addon changed: {relative}')

    verify_runtime()
    for relative, expected in plan['bag_hashes'].items():
        digest = hashlib.sha256()
        with (bag / relative).open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)
        if digest.hexdigest() != expected:
            raise RuntimeError(f'Board bag hash mismatch: {relative}')
    # Add workspace data/results without modifying the accepted runtime files.
    data = runtime / 'data/euroc/MH_01_easy_ros2'
    data.parent.mkdir(parents=True, exist_ok=True)
    if data.is_symlink():
        if data.resolve() != bag:
            raise RuntimeError('Runtime data points to another bag')
    elif data.exists():
        raise RuntimeError('Refusing to overwrite runtime data')
    else:
        data.symlink_to(bag, target_is_directory=True)
    output_root = runtime / 'results/ros2'
    output_root.mkdir(parents=True, exist_ok=True)
    shutil.copy2(payload / 'bag_conversion.json', output_root / 'bag_conversion.json')
    shutil.copy2(payload / 'plan.json', logs / 'plan.json')
    state = dict(status='running', completed=[], bag_hashes_verified=True)
    stop = threading.Event()

    def telemetry():
        paths = sorted([*Path('/sys/class/thermal').glob('thermal_zone*/temp'),
                        *Path('/sys/devices/system/cpu/cpufreq').glob('policy*/scaling_cur_freq'),
                        *Path('/sys/class/devfreq').glob('*dmc*/cur_freq')])
        with (logs / 'telemetry.jsonl').open('w') as stream:
            while not stop.is_set():
                values = {}
                for path in paths:
                    try:
                        values[str(path)] = path.read_text().strip()
                    except OSError:
                        values[str(path)] = None
                stream.write(json.dumps(dict(monotonic_s=time.monotonic(), values=values)) + '\n')
                stream.flush()
                stop.wait(1)

    sampler = threading.Thread(target=telemetry)
    sampler.start()
    try:
        for trial in plan['trials']:
            verify_runtime()
            state['current'] = trial
            (logs / 'state.json').write_text(json.dumps(state, indent=2) + '\n')
            env = os.environ.copy()
            env['RMW_IMPLEMENTATION'] = trial['rmw']
            if trial['rmw'] != 'rmw_cyclonedds_cpp':
                env.pop('CYCLONEDDS_URI', None)
            command = ['/usr/bin/python3', str(runtime / 'VINS-Fusion/infra/desktop/scripts/run_ros2_euroc.py'),
                       '--name', trial['name'], '--mode', trial['mode'], '--deployment', trial['deployment'],
                       '--image-mode', trial['image'], '--image-transport', trial['transport']]
            if trial['pmu']:
                command.append('--perf-counters')
            try:
                with (logs / (trial['name'] + '.log')).open('w') as log:
                    code = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, env=env).returncode
            finally:
                output = output_root / trial['name']
                if output.exists():
                    shutil.copytree(output, logs / trial['name'])
            if code:
                raise RuntimeError(f'{trial["name"]}: runner exit {code}')
            run = json.loads((output / 'run.json').read_text())
            expected = dict(img0=3682, img1=3682 if trial['mode'] == 'stereo_imu' else 0,
                            imu=36820, processed=3682)
            if not run['success'] or run['sensor_counts'] != expected:
                raise RuntimeError('Incomplete VIO input or unsuccessful runner')
            vins_log = (output / 'vins.log').read_text()
            if 'failure detection' in vins_log or 'throw img' in vins_log:
                raise RuntimeError('Tracking reset or pairing drop')
            state['completed'].append(trial['name'])
            (logs / 'state.json').write_text(json.dumps(state, indent=2) + '\n')
            time.sleep(10)
        verify_runtime()
        state['status'] = 'complete'
    except BaseException as error:
        state.update(status='failed', failure=f'{type(error).__name__}: {error}')
        raise
    finally:
        stop.set()
        sampler.join()
        (logs / 'state.json').write_text(json.dumps(state, indent=2) + '\n')


if __name__ == '__main__':
    main()
