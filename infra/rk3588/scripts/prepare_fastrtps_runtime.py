"""Package the pinned Fast DDS addon without changing the accepted base runtime."""
import hashlib
import json
from pathlib import Path
import shutil

from bundle_elf import needed, SYSTEM_LIBS
from prepare_ros2_runtime import copy_runtime, REPO, WORKSPACE


def main():
    base = WORKSPACE / '.infra/rk3588/ros2-payload'
    addon = REPO / 'dependencies/sysroots/ros2-fastrtps/root/opt/ros/humble'
    output = WORKSPACE / '.infra/rk3588/fastrtps-payload'
    output.mkdir(parents=True, exist_ok=False)
    copy_runtime(addon, output / 'ros')
    base_dirs = [base / '.infra/runtime/lib', base / '.infra/ros2/lib',
                 base / '.infra/ros2_ws/install/lib']
    for path in (output / 'ros').rglob('*'):
        if path.is_file():
            with path.open('rb') as stream:
                elf = stream.read(4) == b'\x7fELF'
            if elf:
                for soname in needed(path):
                    if soname not in SYSTEM_LIBS and not (output / 'ros/lib' / soname).is_file() and not any((d / soname).is_file() for d in base_dirs):
                        raise RuntimeError(f'Fast DDS addon dependency missing: {soname}')
    manifest = {str(path.relative_to(output)): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in sorted(output.rglob('*')) if path.is_file()}
    (output / 'files.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'Fast DDS addon: {len(manifest)} files, dependency closure available in addon + accepted runtime')


if __name__ == '__main__':
    main()
