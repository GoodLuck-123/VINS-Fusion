"""Fetch pinned sources and the Ubuntu 22.04 x86-to-ARM ROS 2 SDK, without sudo."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tarfile
import tempfile

REPO = Path(__file__).resolve().parents[2]
DEPS = REPO / 'dependencies'


def digest(path):
    sha = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            sha.update(block)
    return sha.hexdigest()


def fetch(record, cache, reuse, offline):
    destination = cache / record['file']
    if destination.name != record['file']:
        raise ValueError('Cache filenames must be basenames')
    if destination.exists():
        if digest(destination) != record['sha256']:
            raise RuntimeError(f'Checksum mismatch; preserve and inspect {destination}')
        return destination
    partial = destination.with_name(destination.name + '.part')
    try:
        for directory in reuse:
            candidate = directory / destination.name
            if candidate.is_file() and digest(candidate) == record['sha256']:
                shutil.copyfile(candidate, partial)
                break
        else:
            if offline:
                raise RuntimeError(f'Offline cache missing: {destination.name}')
            print('Download:', destination.name, flush=True)
            subprocess.run(['curl', '--fail', '--location', '--retry', '3',
                            '--connect-timeout', '20', '--output', str(partial),
                            record['url']], check=True)
        if digest(partial) != record['sha256']:
            raise RuntimeError(f'Download checksum mismatch: {partial}')
        os.replace(partial, destination)
    finally:
        partial.unlink(missing_ok=True)
    return destination


def unpack_source(archive, destination, sha):
    marker = destination / '.vins-source-sha256'
    if destination.exists():
        if not marker.is_file() or marker.read_text().strip() != sha:
            raise RuntimeError(f'Existing source has a different lock: {destination}')
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.extract-', dir=destination.parent) as tmp:
        stage = Path(tmp)
        with tarfile.open(archive) as source:
            members = source.getmembers()
            roots = {Path(m.name).parts[0] for m in members if m.name}
            if len(roots) != 1:
                raise RuntimeError('Source archive must have exactly one top directory')
            for member in members:
                path = Path(member.name)
                if path.is_absolute() or '..' in path.parts or not (member.isfile() or member.isdir()):
                    raise RuntimeError(f'Unsupported source archive entry: {member.name}')
            # Validation above excludes links, devices and escaping paths on Python 3.10 too.
            if hasattr(tarfile, 'data_filter'):
                source.extractall(stage, filter='data')
            else:
                source.extractall(stage)
        root = stage / roots.pop()
        (root / marker.name).write_text(sha + '\n')
        os.replace(root, destination)


def relocate_sysroot_links(root):
    """Absolute target links must resolve inside a sysroot, never on the host."""
    changes = {}
    for path in sorted(root.rglob('*')):
        if not path.is_symlink():
            continue
        target = os.readlink(path)
        if target.startswith('/'):
            relative = os.path.relpath(root / os.path.normpath(target).lstrip('/'), path.parent)
            replacement = path.with_name(path.name + '.vins-link-tmp')
            replacement.symlink_to(relative)
            os.replace(replacement, path)
            changes[str(path.relative_to(root))] = dict(original=target, relocated=relative)
    audit = root / '.vins-sysroot-links.json'
    if changes or not audit.exists():
        previous = json.loads(audit.read_text()) if audit.exists() else {}
        previous.update(changes)
        audit.write_text(json.dumps(previous, indent=2) + '\n')


def unpack_packages(lock, archives, destination, sysroot=False):
    lock_sha = digest(lock)
    marker = destination / '.vins-lock-sha256'
    if destination.exists():
        if not marker.is_file() or marker.read_text().strip() != lock_sha:
            raise RuntimeError(f'Existing SDK has a different lock: {destination}')
        if sysroot:
            relocate_sysroot_links(destination)
            relocate_ros_python_exports(destination)
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.extract-', dir=destination.parent) as tmp:
        for archive in archives:
            subprocess.run(['dpkg-deb', '--extract', str(archive), tmp], check=True)
        if sysroot:
            relocate_sysroot_links(Path(tmp))
            relocate_ros_python_exports(Path(tmp))
        (Path(tmp) / marker.name).write_text(lock_sha + '\n')
        os.replace(tmp, destination)


def relocate_ros_python_exports(root):
    # Humble message exports contain a literal target libpython link path.
    # CMake does not automatically reroot INTERFACE_LINK_LIBRARIES entries.
    original = '/usr/lib/aarch64-linux-gnu/libpython3.10.so'
    changed = {}
    for path in sorted((root / 'opt/ros/humble/share').rglob('*.cmake')):
        content = path.read_text()
        if original in content and '${CMAKE_SYSROOT}' + original not in content:
            updated = content.replace(original, '${CMAKE_SYSROOT}' + original)
            path.write_text(updated)
            changed[str(path.relative_to(root))] = dict(
                original_sha256=hashlib.sha256(content.encode()).hexdigest(),
                relocated_sha256=hashlib.sha256(updated.encode()).hexdigest())
    audit = root / '.vins-python-cmake-relocations.json'
    if changed or not audit.exists():
        previous = json.loads(audit.read_text()) if audit.exists() else {}
        previous.update(changed)
        audit.write_text(json.dumps(previous, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources-only', action='store_true', help='Skip cross compiler and ARM ROS 2 SDK')
    parser.add_argument('--cache-from', type=Path, action='append', default=[],
                        help='Reuse matching archives from an existing directory; repeatable')
    parser.add_argument('--offline', action='store_true', help='Require all archives in local caches')
    args = parser.parse_args()
    if not args.sources_only and (platform.system(), platform.machine()) != ('Linux', 'x86_64'):
        parser.error('The pinned compiler runs on Linux x86_64; use --sources-only elsewhere')
    cache = DEPS / 'cache'
    cache.mkdir(parents=True, exist_ok=True)
    with (DEPS / '.fetch.lock').open('w') as guard:
        fcntl.flock(guard, fcntl.LOCK_EX)
        sources = json.loads((DEPS / 'sources.lock.json').read_text())['sources']
        for source in sources:
            archive = fetch(source, cache, args.cache_from, args.offline)
            unpack_source(archive, DEPS / 'sources' / source['id'] / source['version'], source['sha256'])
        if not args.sources_only:
            for name, destination in [('toolchain', DEPS / 'toolchain/root'),
                                      ('ros2-sdk', DEPS / 'sysroots/ros2-humble/root')]:
                lock = DEPS / 'locks' / (name + '.json')
                packages = json.loads(lock.read_text())['packages']
                archives = [fetch(p, cache, args.cache_from, args.offline) for p in packages]
                unpack_packages(lock, archives, destination, sysroot=name == 'ros2-sdk')
                print(f'{name}: {len(packages)} pinned package hashes verified', flush=True)
        print('Dependencies ready; downloaded trees and caches are ignored by Git', flush=True)


if __name__ == '__main__':
    main()
