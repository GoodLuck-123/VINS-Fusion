#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
source "$repo/infra/rk3588/scripts/cross_env.sh"
export VINS_ARM_ROS_PREFIX="$(dirname "$repo")/.infra/rk3588/ros2_ws_overlay/install"
ros="$VINS_ARM_SYSROOT/opt/ros/humble"
export AMENT_PREFIX_PATH="$VINS_ARM_ROS_PREFIX:$ros"
export PYTHONPATH="$ros/local/lib/python3.10/dist-packages:$ros/lib/python3.10/site-packages:$VINS_ARM_SYSROOT/usr/lib/python3/dist-packages"
build="$(dirname "$repo")/.infra/rk3588/shared-probe-build"
payload="${VINS_SHARED_PROBE_PAYLOAD:-$(dirname "$repo")/.infra/rk3588/shared-probe-payload}"
cmake -S "$repo/infra/rk3588/probes/shared" -B "$build" \
  -DCMAKE_TOOLCHAIN_FILE="$repo/infra/rk3588/cmake/aarch64.cmake" \
  -DCMAKE_BUILD_TYPE=Release -DPython3_EXECUTABLE=/usr/bin/python3 \
  -DCMAKE_PREFIX_PATH="$VINS_ARM_ROS_PREFIX;$VINS_ARM_PREFIX;$ros;$VINS_ARM_SYSROOT/usr" \
  -Dcv_bridge_DIR="$VINS_ARM_ROS_PREFIX/share/cv_bridge/cmake" \
  -DOpenCV_DIR="$VINS_ARM_PREFIX/lib/cmake/opencv4"
cmake --build "$build" -j "${VINS_BUILD_JOBS:-4}"
python3 "$repo/infra/rk3588/scripts/bundle_elf.py" "$build/shared_probe" \
  --sysroot "$VINS_ARM_SYSROOT" --library-dir "$VINS_ARM_ROS_PREFIX/lib" \
  --library-dir "$VINS_ARM_PREFIX/lib" --library-dir "$ros/lib" --output "$payload"
