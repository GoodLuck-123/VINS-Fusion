"""Verify deployment hashes, imports, standalone and component lifecycle without bag input."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
LOGS = Path(os.environ['VINS_REMOTE_ROOT']) / 'logs'
sys.path.insert(0, str(ROOT / 'VINS-Fusion/infra/desktop/scripts'))


def main():
    manifest = json.loads((ROOT / 'files.json').read_text())
    for relative, digest in manifest.items():
        if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != digest:
            raise RuntimeError(f'Deployment hash mismatch: {relative}')
    import rclpy
    from rclpy.node import Node
    import rosbag2_py
    from composition_interfaces.srv import UnloadNode
    from sensor_msgs.msg import Image, Imu
    from component_tools import load_component
    config = (ROOT / 'VINS-Fusion/config/euroc/euroc_stereo_imu_config.yaml').read_text()
    for key in ['output_path', 'pose_graph_save_path']:
        config = re.sub(rf'^{key}:.*$', f'{key}: "{LOGS}"', config, flags=re.M)
    (LOGS / 'config.yaml').write_text(config)
    for name in ['cam0_mei.yaml', 'cam1_mei.yaml']:
        shutil.copy2(ROOT / 'VINS-Fusion/config/euroc' / name, LOGS / name)
    rclpy.init()
    observer = Node('rk_runtime_observer')
    results = {'verified_files': len(manifest), 'rmw': os.environ['RMW_IMPLEMENTATION'],
               'python': sys.version, 'source': json.loads((ROOT / 'build_source.json').read_text())}
    try:
        for kind in ['standalone', 'component']:
            binary = (ROOT / '.infra/ros2_ws/install/lib/vins/vins_node' if kind == 'standalone'
                      else Path(os.environ['VINS_ROS_PREFIX']) / 'lib/rclcpp_components/component_container')
            ldd = subprocess.check_output(['ldd', str(binary)], text=True)
            (LOGS / f'{kind}_ldd.txt').write_text(ldd)
            if 'not found' in ldd or re.search(r'libopencv_.*\.so\.4\.5', ldd):
                raise RuntimeError(f'Invalid board linkage: {kind}')
            command = [str(binary)]
            if kind == 'standalone':
                command += [str(LOGS / 'config.yaml'), '--ros-args', '-p', 'use_sim_time:=true']
            else:
                command += ['--ros-args', '-r', '__node:=rk_smoke_container']
            with (LOGS / f'{kind}.log').open('w') as log:
                process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                try:
                    if kind == 'component':
                        node_id = load_component(observer, 'rk_smoke_container', 'vins_ros::VinsNode',
                                                 {'config_file': str(LOGS / 'config.yaml'), 'use_sim_time': True}, 'vins_estimator')
                    deadline = time.monotonic() + 30
                    while not all(observer.count_subscribers(topic) for topic in ['/cam0/image_raw', '/cam1/image_raw', '/imu0']):
                        if process.poll() is not None or time.monotonic() > deadline:
                            raise RuntimeError(f'{kind} did not create subscriptions')
                        rclpy.spin_once(observer, timeout_sec=0.2)
                    (LOGS / f'{kind}_maps.txt').write_text(Path(f'/proc/{process.pid}/maps').read_text())
                    if kind == 'component':
                        client = observer.create_client(UnloadNode, '/rk_smoke_container/_container/unload_node')
                        try:
                            if not client.wait_for_service(timeout_sec=10):
                                raise RuntimeError('Unload service unavailable')
                            future = client.call_async(UnloadNode.Request(unique_id=node_id))
                            rclpy.spin_until_future_complete(observer, future, timeout_sec=20)
                            if not future.done() or not future.result().success:
                                raise RuntimeError('Component unload failed')
                        finally:
                            observer.destroy_client(client)
                finally:
                    if process.poll() is None:
                        os.killpg(process.pid, signal.SIGINT)
                    try:
                        code = process.wait(timeout=20)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait()
                        raise RuntimeError(f'{kind} shutdown timed out')
                if code != 0:
                    raise RuntimeError(f'{kind} exit {code}')
                results[kind] = {'exit_code': code, 'subscriptions_ready': True,
                                 'unloaded': kind == 'component'}
    finally:
        observer.destroy_node()
        rclpy.shutdown()
    (LOGS / 'validation.json').write_text(json.dumps(results, indent=2) + '\n')
    print('ARM_ROS2_RUNTIME_OK standalone + component; no VIO input in this probe')


if __name__ == '__main__':
    main()
