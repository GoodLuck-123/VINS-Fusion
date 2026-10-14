"""Package the cross-built VIO runtime, not the SDK or source tree."""
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
        if not path.is_file() or any(part in {'include', 'cmake', 'pkgconfig', '__pycache__',
                                              'tests', 'test', 'support_files', 'models'}
                                     for part in relative.parts):
            continue
        if path.suffix in {'.a', '.pyc'} or path.name.startswith('kitti_'):
            continue
        if sdk and ('cv_bridge' in relative.parts or path.name.startswith('libcv_bridge')):
            continue
        if relative.parts[0].startswith('cv2'):
            continue
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=WORKSPACE / '.infra/rk3588/ros2-payload')
    parser.add_argument('--build-commit', required=True,
                        help='Source commit of the accepted, clean ROS 2 cross build')
    args = parser.parse_args()
    build_commit = subprocess.check_output(['git', '-C', str(REPO), 'rev-parse', args.build_commit], text=True).strip()
    core = ['camera_models', 'vins_estimator', 'loop_fusion', 'global_fusion', 'ros2', 'config']
    if subprocess.check_output(['git', '-C', str(REPO), 'diff', build_commit, '--', *core]):
        raise RuntimeError('Core/config differ from build commit; rebuild before packaging')
    install = WORKSPACE / '.infra/rk3588/ros2_ws_overlay/install'
    legacy = WORKSPACE / '.infra/rk3588/legacy'
    sysroot = REPO / 'dependencies/sysroots/ros2-humble/root'
    ros = sysroot / 'opt/ros/humble'
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    copy_runtime(install, output / '.infra/ros2_ws/install')
    copy_runtime(ros, output / '.infra/ros2', sdk=True)
    copy_runtime(sysroot / 'usr/lib/python3/dist-packages', output / '.infra/runtime/python')
    shutil.copytree(REPO / 'config/euroc', output / 'VINS-Fusion/config/euroc')
    scripts = output / 'VINS-Fusion/infra/desktop/scripts'
    scripts.mkdir(parents=True)
    for path in (REPO / 'infra/desktop/scripts').glob('*.py'):
        shutil.copy2(path, scripts / path.name)
    for name in ['runtime_env.sh', 'ros2_runtime_smoke.py']:
        shutil.copy2(Path(__file__).parent / name, output / name)
    shutil.copy2(REPO / 'infra/desktop/cyclonedds_native.xml', output / 'cyclonedds.xml')
    metadata = {'source_commit': build_commit, 'source_modified': False,
                'packaging_commit': subprocess.check_output(['git', '-C', str(REPO), 'rev-parse', 'HEAD'], text=True).strip(),
                'core_config_blobs': subprocess.check_output(['git', '-C', str(REPO), 'ls-tree', '-r', build_commit, '--', *core], text=True).splitlines()}
    (output / 'build_source.json').write_text(json.dumps(metadata, indent=2) + '\n')
    # Scan all packaged ELF (including dynamically loaded plugins/Python modules),
    # not just DT_NEEDED of the executable. Keep the board's glibc ABI unit intact.
    pending = []
    for path in sorted(output.rglob('*')):
        if path.is_file():
            with path.open('rb') as stream:
                elf = stream.read(4) == b'\x7fELF'
            if elf:
                pending.extend(needed(path))
    dirs = [install / 'lib', legacy / 'lib', ros / 'lib',
            sysroot / 'usr/lib/aarch64-linux-gnu', sysroot / 'lib/aarch64-linux-gnu',
            sysroot / 'usr/lib/aarch64-linux-gnu/blas',
            sysroot / 'usr/lib/aarch64-linux-gnu/lapack', sysroot / 'usr/lib']
    bundled = set()
    lib = output / '.infra/runtime/lib'
    lib.mkdir(parents=True)
    while pending:
        soname = pending.pop()
        if soname in SYSTEM_LIBS or soname in bundled:
            continue
        if Path(soname).name != soname or ('libopencv_' in soname and not soname.endswith('.4.2')):
            raise RuntimeError(f'Unexpected library: {soname}')
        source = next((directory / soname for directory in dirs if (directory / soname).is_file()), None)
        if source is None:
            raise RuntimeError(f'Missing ARM runtime library: {soname}')
        pending.extend(needed(source))
        shutil.copy2(source, lib / soname)
        bundled.add(soname)
    manifest = {str(path.relative_to(output)): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in sorted(output.rglob('*')) if path.is_file()}
    (output / 'files.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'{output}: {len(manifest)} files; {len(bundled)} runtime libraries; board glibc retained')


if __name__ == '__main__':
    main()
