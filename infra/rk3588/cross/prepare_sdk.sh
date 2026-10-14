#!/usr/bin/env bash
set -euo pipefail
test "$(uname -m)" = x86_64
test ! -f /work/sdk-ready || { echo 'SDK already frozen; use it without downloading again' >&2; exit 1; }
mkdir -p /work/downloads/arm64 /work/sysroot /work/smoke
dpkg --add-architecture arm64
sed -i 's/^deb /deb [arch=amd64] /' /etc/apt/sources.list
cat > /etc/apt/sources.list.d/arm64.list <<'EOF'
deb [arch=arm64] http://ports.ubuntu.com/ubuntu-ports jammy main universe restricted multiverse
deb [arch=arm64] http://ports.ubuntu.com/ubuntu-ports jammy-updates main universe restricted multiverse
deb [arch=arm64] http://ports.ubuntu.com/ubuntu-ports jammy-security main universe restricted multiverse
deb [arch=arm64 signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu jammy main
EOF
apt-get update
: > /work/arm64-status
# An empty target dpkg status obtains the complete dependency closure rather
# than treating amd64 build-host packages as already-installed target libraries.
apt-get -y --download-only -o APT::Architecture=arm64 \
  -o Dir::State::status=/work/arm64-status \
  -o Dir::Cache::archives=/work/downloads/arm64 install \
  ros-humble-ros-base:arm64 ros-humble-rmw-cyclonedds-cpp:arm64 \
  ros-humble-cv-bridge:arm64 libboost-all-dev:arm64 libeigen3-dev:arm64 \
  libgoogle-glog-dev:arm64 libsuitesparse-dev:arm64 libblas-dev:arm64 \
  liblapack-dev:arm64 libssl-dev:arm64 libelf-dev:arm64 libdw-dev:arm64 \
  libunwind-dev:arm64 python3-dev:arm64
for package in /work/downloads/arm64/*.deb; do
  architecture=$(dpkg-deb -f "$package" Architecture)
  case "$architecture" in arm64|all) ;; *) echo "Unexpected target package: $package ($architecture)" >&2; exit 1 ;; esac
  dpkg-deb -x "$package" /work/sysroot
done
python3 - <<'PY'
import hashlib, json, pathlib, subprocess
root = pathlib.Path('/work')
packages = []
versions = {}
for p in sorted((root / 'downloads/arm64').glob('*.deb')):
    metadata = subprocess.check_output(['dpkg-deb', '-f', str(p), 'Package', 'Version', 'Architecture'], text=True)
    name = subprocess.check_output(['dpkg-deb', '-f', str(p), 'Package'], text=True).strip()
    version = subprocess.check_output(['dpkg-deb', '-f', str(p), 'Version'], text=True).strip()
    if name in versions and versions[name] != version:
        raise RuntimeError('Multiple versions in target cache: ' + name)
    versions[name] = version
    packages.append(dict(file=p.name, sha256=hashlib.sha256(p.read_bytes()).hexdigest(), control=metadata.strip()))
(root / 'packages.json').write_text(json.dumps(packages, indent=2) + '\n')
PY
cat > /work/smoke/hello.cpp <<'EOF'
#include <iostream>
int main() {
#ifndef __aarch64__
#error "Expected a real aarch64 compiler target"
#endif
    std::cout << "AARCH64_CROSS_OK pointer_bytes=" << sizeof(void*)
              << " compiler=" << __VERSION__ << '\n';
}
EOF
aarch64-linux-gnu-g++ --sysroot=/work/sysroot -O2 /work/smoke/hello.cpp -o /work/smoke/hello
aarch64-linux-gnu-readelf -h -d /work/smoke/hello > /work/smoke/elf.txt
printf '%s\n' "$(uname -m)" > /work/smoke/build_host_arch
aarch64-linux-gnu-g++ --version > /work/smoke/compiler.txt
cp /usr/share/keyrings/ros-archive-keyring.gpg /work/ros-archive-keyring.gpg
touch /work/sdk-ready
if [[ -n "${VINS_HOST_UID:-}" && -n "${VINS_HOST_GID:-}" ]]; then
  chown -R "$VINS_HOST_UID:$VINS_HOST_GID" /work
fi
printf 'ARM SDK prepared; target packages: '
find /work/downloads/arm64 -maxdepth 1 -name '*.deb' | wc -l
