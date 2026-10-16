"""Verify the cross-built ROS 1 executable closure and target compile paths."""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
from bundle_elf import needed, SYSTEM_LIBS

REPO = Path(__file__).resolve().parents[3]
WORKSPACE = REPO.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workspace', type=Path, default=WORKSPACE / '.infra/rk3588/ros1_ws')
    parser.add_argument('--core-reference', default='8c7c8d2', help='Committed core/config built in this workspace')
    args = parser.parse_args()
    core_reference = subprocess.check_output(['git', '-C', str(REPO), 'rev-parse', args.core_reference+'^{commit}'], text=True).strip()
    sdk = REPO / 'dependencies/sysroots/ros1-noetic/root'
    workspace = args.workspace.resolve()
    legacy = WORKSPACE / '.infra/rk3588/ros1-legacy'
    directories = [workspace / 'devel/lib', legacy / 'lib', sdk / 'opt/ros/noetic/lib',
                   workspace / 'build/global_fusion/ThirdParty/GeographicLib',
                   sdk / 'usr/lib/aarch64-linux-gnu', sdk / 'lib/aarch64-linux-gnu',
                   sdk / 'usr/lib/aarch64-linux-gnu/blas', sdk / 'usr/lib/aarch64-linux-gnu/lapack']
    binaries = [workspace / 'devel/lib' / name for name in
                ['camera_models/Calibrations', 'vins/vins_node', 'vins/kitti_odom_test',
                 'vins/kitti_gps_test', 'loop_fusion/loop_fusion_node', 'global_fusion/global_fusion_node']]
    pending = binaries.copy()
    elf_files = {}
    while pending:
        path = pending.pop().resolve()
        if str(path) in elf_files:
            continue
        libraries = needed(path)
        elf_files[str(path)] = dict(sha256=hashlib.sha256(path.read_bytes()).hexdigest(), needed=libraries)
        for soname in libraries:
            if soname in SYSTEM_LIBS:
                continue
            if Path(soname).name != soname or (soname.startswith('libopencv_') and not soname.endswith('.4.2')):
                raise RuntimeError(f'Unexpected target library: {soname}')
            source = next((d / soname for d in directories if (d / soname).is_file()), None)
            if source is None:
                raise RuntimeError(f'Missing target library: {soname}')
            pending.append(source)
    commands = {}
    for package in ['cv_bridge', 'camera_models', 'vins_estimator', 'loop_fusion', 'global_fusion']:
        path = workspace / 'build' / package / 'compile_commands.json'
        entries = json.loads(path.read_text())
        for entry in entries:
            command = entry['command']
            tokens = shlex.split(command)
            if '--sysroot=' + str(sdk) not in tokens:
                raise RuntimeError(f'Missing target sysroot: {entry["file"]}')
            if '-I/usr/include' in tokens or '-isystem /usr/include' in command:
                raise RuntimeError(f'Host headers in target build: {entry["file"]}')
            if str(sdk / 'usr/include/opencv4') in command or str(sdk / 'opt/ros/noetic/include/cv_bridge') in command:
                raise RuntimeError(f'SDK visual library mixed into build: {entry["file"]}')
        commands[package] = dict(units=len(entries), sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    # C++ sources remain byte-identical to the locked cv_bridge archive.
    source = REPO / 'dependencies/sources/cv_bridge_ros1/1.16.2/cv_bridge'
    for path in source.rglob('*.cpp'):
        if path.read_bytes() != (workspace / 'cv_bridge_source' / path.relative_to(source)).read_bytes():
            raise RuntimeError('cv_bridge C++ source changed')
    core = ['camera_models', 'vins_estimator', 'loop_fusion', 'global_fusion', 'config']
    if subprocess.check_output(['git', '-C', str(REPO), 'diff', core_reference, '--', *core]):
        raise RuntimeError('ROS 1 core/config differ from master reference')
    result = dict(status='pass', binaries=[str(p) for p in binaries], elf_files=elf_files,
                  compile_commands=commands, core_reference=core_reference,
                  sdk_lock_sha256=(sdk / '.vins-lock-sha256').read_text().strip(),
                  builder_sha256=hashlib.sha256(Path(__file__).with_name('build_ros1_cross.sh').read_bytes()).hexdigest(),
                  cv_bridge_python_extension=False, board_validation='pending')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as stream:
        stream.write(json.dumps(result, indent=2) + '\n')
    print(f'PASS: {len(binaries)} executables, {len(elf_files)} ARM ELF closure, five package compile paths; board validation pending')


if __name__ == '__main__':
    main()
