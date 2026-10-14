"""Package original ARM ROS 1 VIO with private Python 3.8 and no board glibc."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from bundle_elf import needed, SYSTEM_LIBS

REPO = Path(__file__).resolve().parents[3]
WORKSPACE = REPO.parent


def copy_runtime(source, destination, sdk=False):
    for path in sorted(source.rglob('*')):
        relative = path.relative_to(source)
        if not path.is_file() or any(part in {'include', 'cmake', 'pkgconfig', '__pycache__', 'tests', 'test'} for part in relative.parts):
            continue
        if path.suffix in {'.a', '.pyc'} or (sdk and ('cv_bridge' in relative.parts or path.name.startswith(('libcv_bridge', 'cv2')))):
            continue
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        # ROS launchers must select private target Python via PATH, not board 3.10.
        if path.read_bytes().startswith(b'#!/usr/bin/python3\n'):
            target.write_bytes(target.read_bytes().replace(b'#!/usr/bin/python3\n', b'#!/usr/bin/env python3\n', 1))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=WORKSPACE / '.infra/rk3588/ros1-payload')
    parser.add_argument('--build-commit', required=True)
    args = parser.parse_args()
    build_commit = subprocess.check_output(['git', '-C', str(REPO), 'rev-parse', args.build_commit + '^{commit}'], text=True).strip()
    core = ['camera_models', 'vins_estimator', 'loop_fusion', 'global_fusion', 'config']
    if subprocess.check_output(['git', '-C', str(REPO), 'diff', build_commit, '--', *core]):
        raise RuntimeError('Core/config changed since accepted cross build')
    validation = json.loads((REPO / 'infra/rk3588/reference/ros1_cross_build_20261014/validation.json').read_text())
    for name, item in validation['elf_files'].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest() != item['sha256']:
            raise RuntimeError(f'Accepted build changed: {name}')
    workspace = WORKSPACE / '.infra/rk3588/ros1_ws'
    legacy = WORKSPACE / '.infra/rk3588/ros1-legacy'
    sdk = REPO / 'dependencies/sysroots/ros1-noetic/root'
    ros = sdk / 'opt/ros/noetic'
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    copy_runtime(ros, output / '.infra/ros1', sdk=True)
    # roscore.xml invokes rosversion, installed by rospkg under usr/bin.
    launcher = output / '.infra/ros1/bin/rosversion'
    source_launcher = sdk / 'usr/bin/rosversion'
    shutil.copy2(source_launcher, launcher)
    launcher.write_bytes(launcher.read_bytes().replace(b'#!/usr/bin/python3\n', b'#!/usr/bin/env python3\n', 1))
    copy_runtime(sdk / 'usr/lib/python3/dist-packages', output / '.infra/runtime/python', sdk=True)
    copy_runtime(sdk / 'usr/lib/python3.8', output / '.infra/python38/lib/python3.8')
    pybin = output / '.infra/python38/bin'
    pybin.mkdir(parents=True)
    shutil.copy2(sdk / 'usr/bin/python3.8', pybin / 'python3')
    node = output / '.infra/vins_ws/devel/lib/vins/vins_node'
    node.parent.mkdir(parents=True)
    shutil.copy2(workspace / 'devel/lib/vins/vins_node', node)
    shutil.copytree(REPO / 'config/euroc', output / 'VINS-Fusion/config/euroc')
    scripts = output / 'VINS-Fusion/infra/desktop/scripts'
    scripts.mkdir(parents=True)
    for name in ['run_euroc_baseline.py', 'process_metrics.py', 'workspace_paths.py']:
        shutil.copy2(REPO / 'infra/desktop/scripts' / name, scripts / name)
    shutil.copy2(Path(__file__).with_name('ros1_runtime_env.sh'), output / 'runtime_env.sh')
    metadata = dict(source_commit=build_commit, source_modified=False,
                    packaging_commit=subprocess.check_output(['git', '-C', str(REPO), 'rev-parse', 'HEAD'], text=True).strip(),
                    core_config_blobs=subprocess.check_output(['git', '-C', str(REPO), 'ls-tree', '-r', build_commit, '--', *core], text=True).splitlines(),
                    python_version='3.8', cv_bridge_python_extension=False)
    (output / 'build_source.json').write_text(json.dumps(metadata, indent=2) + '\n')
    directories = [workspace / 'devel/lib', legacy / 'lib', ros / 'lib',
                   sdk / 'usr/lib/aarch64-linux-gnu', sdk / 'lib/aarch64-linux-gnu',
                   sdk / 'usr/lib/aarch64-linux-gnu/blas', sdk / 'usr/lib/aarch64-linux-gnu/lapack', sdk / 'usr/lib']
    pending = []
    for path in output.rglob('*'):
        if path.is_file() and path.open('rb').read(4) == b'\x7fELF':
            pending.extend(needed(path))
    lib = output / '.infra/runtime/lib'
    lib.mkdir(parents=True, exist_ok=True)
    copied = set()
    while pending:
        soname = pending.pop()
        if soname in SYSTEM_LIBS or soname in copied:
            continue
        if Path(soname).name != soname or (soname.startswith('libopencv_') and not soname.endswith('.4.2')):
            raise RuntimeError(f'Unexpected ARM library: {soname}')
        source = next((d / soname for d in directories if (d / soname).is_file()), None)
        if source is None:
            raise RuntimeError(f'Missing ARM runtime library: {soname}')
        pending.extend(needed(source))
        shutil.copy2(source, lib / soname)
        copied.add(soname)
    manifest = {str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.rglob('*')) if p.is_file()}
    (output / 'files.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'{output}: {len(manifest)} files, {len(copied)} ARM libraries; system Python/glibc retained')


if __name__ == '__main__':
    main()
