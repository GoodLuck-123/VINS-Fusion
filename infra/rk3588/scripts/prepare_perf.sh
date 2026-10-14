#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
source "$repo/infra/rk3588/scripts/cross_env.sh"
payload="${VINS_PERF_PAYLOAD:-$(dirname "$repo")/.infra/rk3588/perf-payload}"
python3 "$repo/infra/rk3588/scripts/bundle_elf.py" \
  "$VINS_ARM_SYSROOT/usr/lib/linux-tools-5.15.0-198/perf" \
  --sysroot "$VINS_ARM_SYSROOT" --output "$payload"
"$VINS_CROSS_ROOT/usr/bin/aarch64-linux-gnu-g++" --sysroot="$VINS_ARM_SYSROOT" \
  -L"$VINS_ARM_SYSROOT/usr/lib/aarch64-linux-gnu" -O2 -g -fno-omit-frame-pointer \
  "$repo/infra/rk3588/scripts/profile_smoke.cpp" -o "$payload/profile_smoke"
printf 'ARM perf and sampling probe prepared: %s\n' "$payload"
