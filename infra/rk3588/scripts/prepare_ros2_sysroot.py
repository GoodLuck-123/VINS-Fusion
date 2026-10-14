"""Download authenticated ARM Humble/Jammy packages into a private host sysroot."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import pwd
import subprocess

REPO = Path(__file__).resolve().parents[3]
PACKAGES = (
    'ros-humble-ros-base', 'ros-humble-rmw-cyclonedds-cpp', 'ros-humble-cv-bridge',
    'libc6-dev', 'libboost-filesystem-dev', 'libboost-program-options-dev',
    'libboost-system-dev', 'libboost-python-dev', 'libboost-regex-dev',
    'libgoogle-glog-dev', 'libsuitesparse-dev', 'libblas-dev', 'liblapack-dev',
    'libssl-dev', 'libjpeg-dev', 'libpng-dev', 'zlib1g-dev', 'python3-dev',
    'libelf-dev', 'libdw-dev', 'libunwind-dev',
    'linux-tools-generic',
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prefix', type=Path, default=REPO.parent / '.infra/rk3588/ros2-sdk')
    args = parser.parse_args()
    root = args.prefix.resolve()
    if (root / 'ready').exists():
        raise RuntimeError('Preserve the frozen SDK; use a new prefix to resolve again')
    for name in ('state/lists/partial', 'cache/archives/partial', 'sysroot'):
        (root / name).mkdir(parents=True, exist_ok=True)
    key = root / 'ros-archive-keyring.gpg'
    subprocess.run(['curl', '--fail', '--location', '--retry', '3', '--connect-timeout', '10',
                    '--max-time', '90', 'https://raw.githubusercontent.com/ros/rosdistro/master/ros.key',
                    '--output', str(key)], check=True)
    sources = root / 'sources.list'
    ubuntu_key = '/usr/share/keyrings/ubuntu-archive-keyring.gpg'
    sources.write_text(''.join(f'deb [arch=arm64 signed-by={ubuntu_key}] '
                              f'https://ports.ubuntu.com/ubuntu-ports {suite} main universe\n'
                              for suite in ('jammy', 'jammy-updates', 'jammy-security'))
                       + f'deb [arch=arm64 signed-by={key}] http://packages.ros.org/ros2/ubuntu jammy main\n')
    (root / 'state/status').touch()
    apt = ['apt-get', '-o', 'Debug::NoLocking=true', '-o', 'APT::Architecture=arm64',
           '-o', 'APT::Architectures::=arm64', '-o', 'Acquire::Retries=3',
           '-o', 'Acquire::http::Timeout=30', '-o', 'Acquire::https::Timeout=30',
           '-o', 'APT::Sandbox::User=' + pwd.getpwuid(os.getuid()).pw_name,
           '-o', 'Dir::State=' + str(root / 'state'),
           '-o', 'Dir::State::status=' + str(root / 'state/status'),
           '-o', 'Dir::Cache=' + str(root / 'cache'),
           '-o', 'Dir::Etc::sourcelist=' + str(sources), '-o', 'Dir::Etc::sourceparts=-']
    subprocess.run([*apt, 'update'], check=True)
    subprocess.run([*apt, '--download-only', '-y', '--no-install-recommends', 'install',
                    *(name + ':arm64' for name in PACKAGES)], check=True)
    packages = []
    versions = {}
    for package in sorted((root / 'cache/archives').glob('*.deb')):
        fields = {field: subprocess.check_output(['dpkg-deb', '-f', str(package), field], text=True).strip()
                  for field in ('Package', 'Version', 'Architecture')}
        if fields['Architecture'] not in ('arm64', 'all'):
            raise RuntimeError(f'Unexpected host package in target SDK: {package}')
        name, version = fields['Package'], fields['Version']
        if name in versions and versions[name] != version:
            raise RuntimeError(f'Multiple versions in target cache: {name}')
        versions[name] = version
        packages.append(dict(file=package.name, sha256=hashlib.sha256(package.read_bytes()).hexdigest(), **fields))
    if not packages:
        raise RuntimeError('No target packages downloaded')
    for package in packages:
        subprocess.run(['dpkg-deb', '-x', str(root / 'cache/archives' / package['file']),
                        str(root / 'sysroot')], check=True)
    (root / 'packages.json').write_text(json.dumps(packages, indent=2) + '\n')
    (root / 'ready').touch()
    print(f'Frozen ARM ROS 2 sysroot: {root}; {len(packages)} authenticated packages')


if __name__ == '__main__':
    main()
