#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
source "$repo/infra/rk3588/scripts/cross_env.sh"
build="$(dirname "$repo")/.infra/rk3588/ros1-legacy-probe-build"
payload="$(dirname "$repo")/.infra/rk3588/ros1-legacy-probe-payload"
cmake -S "$repo/infra/rk3588/probes/legacy" -B "$build" \
  -DCMAKE_TOOLCHAIN_FILE="$repo/infra/rk3588/cmake/aarch64.cmake" \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH="$VINS_ARM_PREFIX;$VINS_ARM_SYSROOT/usr" \
  -DOpenCV_DIR="$VINS_ARM_PREFIX/lib/cmake/opencv4" \
  -DCeres_DIR="$VINS_ARM_PREFIX/lib/cmake/Ceres" \
  -DEigen3_DIR="$VINS_ARM_PREFIX/share/eigen3/cmake" \
  -DCMAKE_DISABLE_FIND_PACKAGE_TBB=TRUE
cmake --build "$build" -j "${VINS_BUILD_JOBS:-4}"
python3 "$repo/infra/rk3588/scripts/bundle_elf.py" "$build/legacy_smoke" \
  --sysroot "$VINS_ARM_SYSROOT" --library-dir "$VINS_ARM_PREFIX/lib" --output "$payload"
