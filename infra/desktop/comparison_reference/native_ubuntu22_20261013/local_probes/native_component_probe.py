"""Rebuildable lifecycle probe: load, reject duplicate, unload and reload mono/stereo."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import time

import rclpy
from composition_interfaces.srv import LoadNode, UnloadNode, ListNodes
from rcl_interfaces.msg import Parameter, ParameterValue, ParameterType

REPO = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    configs = {}
    for mode in ('mono_imu', 'stereo_imu'):
        text = (REPO / f'config/euroc/euroc_{mode}_config.yaml').read_text()
        text = re.sub(r'^output_path:.*$', f'output_path: "{args.output.resolve()}"', text, flags=re.M)
        text = re.sub(r'^pose_graph_save_path:.*$', f'pose_graph_save_path: "{args.output.resolve()}/pose_graph/"', text, flags=re.M)
        path = args.output / f'euroc_{mode}_config.yaml'
        path.write_text(text)
        configs[mode] = str(path.resolve())
    for name in ('cam0_mei.yaml', 'cam1_mei.yaml'):
        shutil.copy2(REPO / 'config/euroc' / name, args.output / name)
    result = {'status': 'running', 'cycles': [], 'rmw': os.environ.get('RMW_IMPLEMENTATION')}
    container = None
    node = None
    try:
        with (args.output / 'container.log').open('x') as log:
            container = subprocess.Popen([str(Path(os.environ['CONDA_PREFIX']) / 'lib/rclcpp_components/component_container'),
                            '--ros-args', '-r', '__node:=native_lifecycle_container'],
                            stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            rclpy.init()
            node = rclpy.create_node('native_lifecycle_probe')
            clients = {name: node.create_client(kind, '/native_lifecycle_container/_container/' + name)
                       for name, kind in (('load_node', LoadNode), ('unload_node', UnloadNode), ('list_nodes', ListNodes))}
            for client in clients.values():
                if not client.wait_for_service(timeout_sec=20):
                    raise RuntimeError('Container service unavailable')

            def call(name, request):
                future = clients[name].call_async(request)
                rclpy.spin_until_future_complete(node, future, timeout_sec=20)
                if not future.done() or future.exception():
                    raise RuntimeError(f'Component service failed: {name}')
                return future.result()

            def load(config):
                request = LoadNode.Request()
                request.package_name = 'vins'
                request.plugin_name = 'vins_ros::VinsNode'
                request.node_name = 'native_probe_vins'
                request.parameters = [Parameter(name='config_file', value=ParameterValue(
                    type=ParameterType.PARAMETER_STRING, string_value=config))]
                request.extra_arguments = [Parameter(name='use_intra_process_comms', value=ParameterValue(
                    type=ParameterType.PARAMETER_BOOL, bool_value=True))]
                return call('load_node', request)

            for cycle in range(3):
                for mode in ('mono_imu', 'stereo_imu'):
                    loaded = load(configs[mode])
                    if not loaded.success:
                        raise RuntimeError(f'Load failed: {loaded.error_message}')
                    duplicate = load(configs[mode])
                    if duplicate.success or 'Only one VINS' not in duplicate.error_message:
                        raise RuntimeError('Duplicate estimator was not rejected correctly')
                    listing = call('list_nodes', ListNodes.Request())
                    if list(listing.unique_ids) != [loaded.unique_id]:
                        raise RuntimeError('Unexpected active component instances')
                    unloaded = call('unload_node', UnloadNode.Request(unique_id=loaded.unique_id))
                    if not unloaded.success:
                        raise RuntimeError(f'Unload failed: {unloaded.error_message}')
                    if call('list_nodes', ListNodes.Request()).unique_ids:
                        raise RuntimeError('Component remains after unload')
                    result['cycles'].append(dict(cycle=cycle + 1, mode=mode, load=True,
                                                 duplicate_rejected=True, unload=True))
            invalid = load(str(args.output / 'missing-config.yaml'))
            if invalid.success or 'config_file' not in invalid.error_message:
                raise RuntimeError('Invalid configuration was not rejected')
            result.update(status='complete', invalid_config_rejected=True)
    except BaseException as error:
        result.update(status='failed', failure=str(error))
        raise
    finally:
        if node is not None:
            node.destroy_node()
            rclpy.shutdown()
        if container is not None:
            if container.poll() is None:
                os.killpg(container.pid, signal.SIGINT)
                try:
                    container.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    os.killpg(container.pid, signal.SIGKILL)
                    container.wait()
            result['container_exit_code'] = container.returncode
        result['finished_utc'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        (args.output / 'validation.json').write_text(json.dumps(result, indent=2) + '\n')
    if result['container_exit_code'] != 0:
        raise RuntimeError('Container did not exit cleanly')


if __name__ == '__main__':
    main()
