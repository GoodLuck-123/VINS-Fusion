"""Shared validation for the standalone board CLI (Python 3.8+)."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import shutil


class Invalid(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise Invalid(message)


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def install_root(value=None):
    return Path(value or os.environ.get('VINS_INSTALL_ROOT') or Path(__file__).resolve().parents[2]).expanduser().resolve()


def readable(path):
    path = Path(path)
    require(path.is_file(), 'Missing file: ' + str(path))
    with path.open('rb') as stream:
        stream.read(1)
    return path


def yaml_file(path, root):
    # PyYAML is already included in the private runtime. Its pure-Python loader
    # also runs under the board system Python, so basic checks survive a broken
    # private interpreter or ELF dependency.
    bundled = root / 'runtime/python'
    if bundled.is_dir() and str(bundled) not in sys.path:
        sys.path.insert(0, str(bundled))
    import yaml

    class Loader(yaml.SafeLoader):
        pass

    def mapping(loader, node, deep=False):
        result = {}
        for key, value in node.value:
            key = loader.construct_object(key, deep=deep)
            require(key not in result, 'Duplicate YAML key {!r}: {}'.format(key, path))
            result[key] = loader.construct_object(value, deep=deep)
        return result

    Loader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)
    Loader.add_constructor('tag:yaml.org,2002:opencv-matrix', mapping)
    text = readable(path).read_text()
    text = re.sub(r'^%YAML:1\.0\s*$', '', text, flags=re.M)
    data = yaml.load(text, Loader=Loader)
    require(isinstance(data, dict), 'YAML must contain a mapping: ' + str(path))
    return data


def number(data, key, low=None, high=None, integer=False):
    value = data.get(key)
    require(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value), 'Missing or non-finite numeric field: ' + key)
    require(not integer or isinstance(value, int), 'Expected integer: ' + key)
    require(low is None or value >= low, '{} must be >= {}'.format(key, low))
    require(high is None or value <= high, '{} must be <= {}'.format(key, high))
    return value


def matrix(data, key):
    value = data.get(key)
    require(isinstance(value, dict) and value.get('rows') == 4 and value.get('cols') == 4 and value.get('dt') == 'd', 'Expected 4x4 double opencv-matrix: ' + key)
    values = value.get('data', [])
    require(len(values) == 16 and all(isinstance(v, (int, float)) and math.isfinite(v) for v in values), 'Invalid matrix data: ' + key)
    require(all(abs(values[12+i] - v) < 1e-8 for i, v in enumerate([0, 0, 0, 1])), 'Invalid homogeneous last row: ' + key)
    # R^T R and det(R), without adding numpy as a system-Python dependency.
    rot = [values[i:i+3] for i in (0, 4, 8)]
    require(all(abs(sum(rot[k][i]*rot[k][j] for k in range(3)) - (i == j)) < 1e-3 for i in range(3) for j in range(3)), 'Rotation is not orthonormal: ' + key)
    det = sum(rot[0][i]*(rot[1][(i+1)%3]*rot[2][(i+2)%3]-rot[1][(i+2)%3]*rot[2][(i+1)%3]) for i in range(3))
    require(abs(det-1) < 1e-3, 'Rotation determinant must be +1: ' + key)


def configuration(path, root, output=None):
    path = Path(path).expanduser().resolve()
    data = yaml_file(path, root)
    cams = number(data, 'num_of_cam', 1, 2, True)
    imu = number(data, 'imu', 0, 1, True)
    require(cams == 2 or imu == 1, 'Monocular mode requires imu: 1')
    for key in ['multiple_thread', 'show_track', 'flow_back', 'estimate_td']:
        number(data, key, 0, 1, True)
    extrinsic = number(data, 'estimate_extrinsic', 0, 2, True)
    require(extrinsic != 2 or (cams == 1 and imu), 'estimate_extrinsic: 2 supports monocular + IMU only')
    for key in ['image_width', 'image_height', 'max_cnt', 'min_dist', 'max_num_iterations']:
        number(data, key, 1, integer=True)
    for key in ['F_threshold', 'max_solver_time', 'keyframe_parallax']:
        number(data, key, 1e-12)
    number(data, 'td')
    if imu:
        for key in ['acc_n', 'gyr_n', 'acc_w', 'gyr_w', 'g_norm']:
            number(data, key, 1e-12)
    topics = {}
    for key in ['image0_topic'] + (['image1_topic'] if cams == 2 else []) + (['imu_topic'] if imu else []):
        topic = data.get(key)
        require(isinstance(topic, str) and re.fullmatch(r'/[A-Za-z][A-Za-z0-9_/]*', topic) and '//' not in topic and not topic.endswith('/'), 'Use an absolute ROS topic for {}: {!r}'.format(key, topic))
        require(topic not in topics, 'Input topics must be distinct: ' + topic)
        topics[topic] = 'sensor_msgs/Imu' if key == 'imu_topic' else 'sensor_msgs/Image'
    calibrations = []
    for i in range(cams):
        key = 'cam{}_calib'.format(i)
        value = data.get(key)
        require(isinstance(value, str) and value.strip(), 'Missing calibration path: ' + key)
        calib = (path.parent / value).resolve()
        calibration = yaml_file(calib, root)
        require(calibration.get('image_width') == data['image_width'] and calibration.get('image_height') == data['image_height'], 'Calibration image size differs: ' + str(calib))
        model = str(calibration.get('model_type', 'MEI')).upper()
        fields = {'MEI': ('gamma1', 'gamma2', 'u0', 'v0'), 'PINHOLE': ('fx', 'fy', 'cx', 'cy'), 'PINHOLE_FULL': ('fx', 'fy', 'cx', 'cy'), 'SCARAMUZZA': (), 'KANNALA_BRANDT': ('k2', 'k3', 'k4', 'k5', 'mu', 'mv', 'u0', 'v0')}
        require(model in fields, 'Unsupported calibration model {}: {}'.format(model, calib))
        projection = calibration.get('projection_parameters', {})
        for name in fields[model]:
            number(projection, name)
        for name in {'MEI': ('gamma1', 'gamma2'), 'PINHOLE': ('fx', 'fy'), 'PINHOLE_FULL': ('fx', 'fy'), 'SCARAMUZZA': (), 'KANNALA_BRANDT': ('mu', 'mv')}[model]:
            number(projection, name, 1e-12)
        if model == 'MEI':
            number(calibration.get('mirror_parameters', {}), 'xi')
        if model == 'SCARAMUZZA':
            for section, names in [('poly_parameters', ['p'+str(j) for j in range(5)]), ('inv_poly_parameters', ['p'+str(j) for j in range(20)]), ('affine_parameters', ['ac','ad','ae','cx','cy'])]:
                for name in names:
                    number(calibration.get(section, {}), name)
            affine = calibration['affine_parameters']
            require(abs(affine['ac']-affine['ad']*affine['ae']) > 1e-12, 'Singular camera affine transform: '+str(calib))
        if model in ('MEI', 'PINHOLE', 'PINHOLE_FULL'):
            for name in ('k1', 'k2', 'p1', 'p2'):
                number(calibration.get('distortion_parameters', {}), name)
            if model == 'PINHOLE_FULL':
                for name in ('k3','k4','k5','k6'):
                    number(calibration.get('distortion_parameters', {}), name)
        calibrations.append(str(calib))
        if i or extrinsic != 2:
            matrix(data, 'body_T_cam' + str(i))
    # run creates a copy with a concrete output path. Direct checks without an
    # override validate the configured paths rather than pretending ~ expands.
    if output is None:
        for key in ['output_path', 'pose_graph_save_path']:
            value = data.get(key)
            require(isinstance(value, str) and Path(value).is_absolute(), '{} must be an absolute board path (or pass --output): {}'.format(key, path))
    return dict(path=str(path), values=data, topics=topics, calibrations=calibrations)


def directory(path, min_free_mb=512):
    path = Path(path).expanduser().absolute()
    parent = path
    while not parent.exists():
        require(not parent.is_symlink(), 'Broken directory symlink: ' + str(parent))
        parent = parent.parent
    require(parent.is_dir(), 'Path component is not a directory: ' + str(parent))
    with tempfile.TemporaryFile(prefix='.vins-write-check-', dir=str(parent)) as probe:
        probe.write(b'vins'); probe.flush()
    free = shutil.disk_usage(str(parent)).free
    require(free >= min_free_mb * 1024 * 1024, 'Insufficient space at {}: {:.1f} MiB free, {:.1f} MiB required'.format(parent, free/1024/1024, min_free_mb))
    return dict(path=str(path), checked_parent=str(parent), free_bytes=free, min_free_mb=min_free_mb, exists=path.exists())


def environment(root):
    readable(root / 'env.sh')
    result = subprocess.run(['bash', '-c', 'set -e; source "$1"; /usr/bin/env -0', 'vins-cli', str(root/'env.sh')], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
    require(result.returncode == 0, 'Environment initialization failed at {}: {}'.format(root/'env.sh', result.stderr.decode(errors='replace')))
    env = dict(item.decode().split('=', 1) for item in result.stdout.split(b'\0') if b'=' in item)
    require(env.get('VINS_INSTALL_ROOT') == str(root), 'env.sh selected another install: ' + str(root))
    return env


def bag_info(path, config, root, full=False):
    path = readable(Path(path).expanduser().resolve())
    result = subprocess.run(['python3', str(root/'scripts/cli/bag_info.py'), str(path), json.dumps(config['topics']), str(config['values']['td']), 'full' if full else 'endpoints'], env=environment(root), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=600 if full else 60)
    require(result.returncode == 0, 'Bag check failed for {}: {}'.format(path, result.stderr.strip() or result.stdout.strip()))
    return json.loads(result.stdout)


def prepare_config(config, output):
    folder = output/'config'
    folder.mkdir()
    text = Path(config['path']).read_text()
    changes = dict(output_path=str(output), pose_graph_save_path=str(output/'pose_graph'))
    for i, source in enumerate(config['calibrations']):
        name = 'cam{}.yaml'.format(i)
        shutil.copy2(source, folder/name)
        changes['cam{}_calib'.format(i)] = name
    for key, value in changes.items():
        pattern = r'^(?:'+re.escape(key)+r'|"'+re.escape(key)+r'"|\x27'+re.escape(key)+r'\x27)\s*:.*$'
        text, count = re.subn(pattern, lambda match: key+': '+json.dumps(value, ensure_ascii=False), text, flags=re.M)
        require(count == 1, 'Expected one top-level {} field in {}'.format(key, config['path']))
    (output/'pose_graph').mkdir()
    target = folder/'vio.yaml'
    target.write_text(text)
    return target
