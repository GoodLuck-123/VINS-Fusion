#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
workspace=$(dirname "$repo")
prefix="${VINS_CROSS_PREFIX:-$workspace/.infra/rk3588/toolchain}"
test "$(uname -s)" = Linux && test "$(uname -m)" = x86_64
test ! -f "$prefix/ready" || { echo 'Toolchain is already frozen' >&2; exit 1; }
mkdir -p "$prefix/debs/partial" "$prefix/apt-state" "$prefix/apt-cache" "$prefix/root" "$prefix/smoke"
# Read the host's authenticated Ubuntu indexes and package status, but keep all
# downloads, locks, caches and extended state in this private build directory.
apt-get -y --download-only -o Debug::NoLocking=true \
  -o Dir::State="$prefix/apt-state" -o Dir::State::status=/var/lib/dpkg/status \
  -o Dir::State::lists=/var/lib/apt/lists -o Dir::Cache="$prefix/apt-cache" \
  -o Dir::Cache::archives="$prefix/debs" install g++-aarch64-linux-gnu
python3 - "$prefix" <<'PY'
import hashlib, json, pathlib, subprocess, sys
root = pathlib.Path(sys.argv[1])
packages = []
versions = {}
for p in sorted((root / 'debs').glob('*.deb')):
    name = subprocess.check_output(['dpkg-deb', '-f', str(p), 'Package'], text=True).strip()
    version = subprocess.check_output(['dpkg-deb', '-f', str(p), 'Version'], text=True).strip()
    if name in versions and versions[name] != version:
        raise RuntimeError('Multiple versions in compiler cache: ' + name)
    versions[name] = version
    control = subprocess.check_output(['dpkg-deb', '-f', str(p), 'Package', 'Version', 'Architecture'], text=True)
    packages.append(dict(file=p.name, sha256=hashlib.sha256(p.read_bytes()).hexdigest(), control=control.strip()))
if not packages:
    raise RuntimeError('No compiler packages downloaded')
(root / 'packages.json').write_text(json.dumps(packages, indent=2) + '\n')
PY
for package in "$prefix"/debs/*.deb; do dpkg-deb -x "$package" "$prefix/root"; done
export LD_LIBRARY_PATH="$prefix/root/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
compiler="$prefix/root/usr/bin/aarch64-linux-gnu-g++"
test "$("$compiler" -dumpmachine)" = aarch64-linux-gnu
cat > "$prefix/smoke/hello.cpp" <<'EOF'
#include <iostream>
int main() {
#ifndef __aarch64__
#error "Expected an aarch64 target"
#endif
    std::cout << "AARCH64_CROSS_OK pointer_bytes=" << sizeof(void*)
              << " compiler=" << __VERSION__ << '\n';
}
EOF
"$compiler" --sysroot="$prefix/root" -O2 "$prefix/smoke/hello.cpp" -o "$prefix/smoke/hello"
"$prefix/root/usr/bin/aarch64-linux-gnu-readelf" -h -d "$prefix/smoke/hello" > "$prefix/smoke/elf.txt"
printf '%s\n' "$(uname -m)" > "$prefix/smoke/build_host_arch"
"$compiler" --version > "$prefix/smoke/compiler.txt"
"$workspace/.infra/bin/vins-remote" "${VINS_RK_TARGET:-firefly@10.106.0.220}" "$prefix/smoke" \
  --run "$repo/infra/rk3588/scripts/cross_smoke.sh" \
  --output "$workspace/results/rk3588/${VINS_CROSS_SMOKE_NAME:-cross-smoke02}" --timeout 60
touch "$prefix/ready"
printf 'Host cross compiler prepared: %s\n' "$compiler"
