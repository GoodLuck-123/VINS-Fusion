"""Check native ROS 2 extension startup/shutdown and KITTI argument rejection only."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import time

repo = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=False)
config = args.output / 'euroc_stereo_imu_config.yaml'
text = (repo / 'config/euroc/euroc_stereo_imu_config.yaml').read_text()
text = re.sub(r'^output_path:.*$', f'output_path: "{args.output.resolve()}"', text, flags=re.M)
text = re.sub(r'^pose_graph_save_path:.*$', f'pose_graph_save_path: "{args.output.resolve()}/pose_graph/"', text, flags=re.M)
config.write_text(text)
for name in ('cam0_mei.yaml', 'cam1_mei.yaml'):
    shutil.copy2(repo / 'config/euroc' / name, args.output / name)
prefix = repo.parent / '.infra/ros2_ws/install/lib'
records = []
for package, binary in [('loop_fusion', 'loop_fusion_node'), ('global_fusion', 'global_fusion_node')]:
    command = [str(prefix / package / binary)] + ([str(config.resolve())] if package == 'loop_fusion' else [])
    with (args.output / (binary + '.log')).open('x') as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            time.sleep(3)
            if process.poll() is not None:
                raise RuntimeError(f'{binary} exited during startup')
            os.killpg(process.pid, signal.SIGINT)
            code = process.wait(timeout=15)
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
    records.append(dict(binary=binary, survived_startup=True, sigint_exit_code=code))
    if code:
        raise RuntimeError(f'{binary} did not exit cleanly')
for binary in ('kitti_odom_test', 'kitti_gps_test'):
    with (args.output / (binary + '.log')).open('x') as log:
        result = subprocess.run([str(prefix / 'vins' / binary)], stdout=log, stderr=subprocess.STDOUT, timeout=15)
    if result.returncode != 1:
        raise RuntimeError(f'{binary} did not reject missing arguments')
    records.append(dict(binary=binary, missing_arguments_exit_code=result.returncode))
(args.output / 'validation.json').write_text(json.dumps({'status':'complete','checks':records,
    'scope':'Startup/SIGINT or argument validation only; no loop/GNSS/KITTI dataset acceptance'},indent=2)+'\n')
