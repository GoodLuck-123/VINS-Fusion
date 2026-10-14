#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
source "$repo/infra/rk3588/scripts/cross_env.sh"
export VINS_ARM_ROS_PREFIX="${VINS_ARM_ROS_PREFIX:-$(dirname "$repo")/.infra/rk3588/ros2_ws_overlay/install}"
build="$(dirname "$repo")/.infra/rk3588/ros2_ws_overlay/build"
ros="$VINS_ARM_SYSROOT/opt/ros/humble"
export AMENT_PREFIX_PATH="$VINS_ARM_ROS_PREFIX:$ros"
# Only pure Python build helpers are executed on the host. Target Python/NumPy
# headers and libpython are passed explicitly; no ARM Python executable is run.
export PYTHONPATH="$ros/local/lib/python3.10/dist-packages:$ros/lib/python3.10/site-packages:$VINS_ARM_SYSROOT/usr/lib/python3/dist-packages"
test -f "$VINS_ARM_PREFIX/lib/cmake/opencv4/OpenCVConfig.cmake"
test -f "$VINS_ARM_PREFIX/lib/cmake/Ceres/CeresConfig.cmake"
mkdir -p "$build" "$VINS_ARM_ROS_PREFIX"
common=(-G "Unix Makefiles" -DCMAKE_TOOLCHAIN_FILE="$repo/infra/rk3588/cmake/aarch64.cmake"
  -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF -DCMAKE_INSTALL_LIBDIR=lib
  -DCMAKE_INSTALL_PREFIX="$VINS_ARM_ROS_PREFIX"
  -DCMAKE_PREFIX_PATH="$VINS_ARM_ROS_PREFIX;$VINS_ARM_PREFIX;$ros;$VINS_ARM_SYSROOT/usr"
  -DOpenCV_DIR="$VINS_ARM_PREFIX/lib/cmake/opencv4"
  -DCeres_DIR="$VINS_ARM_PREFIX/lib/cmake/Ceres"
  -Dcv_bridge_DIR="$VINS_ARM_ROS_PREFIX/share/cv_bridge/cmake"
  -Dcamera_models_DIR="$VINS_ARM_ROS_PREFIX/share/camera_models/cmake"
  -DEigen3_DIR="$VINS_ARM_PREFIX/share/eigen3/cmake"
  -DPython3_EXECUTABLE=/usr/bin/python3
  -DPython3_INCLUDE_DIR="$VINS_ARM_SYSROOT/usr/include/python3.10"
  -DPython3_LIBRARY="$VINS_ARM_SYSROOT/usr/lib/aarch64-linux-gnu/libpython3.10.so"
  -DPython3_NumPy_INCLUDE_DIR="$VINS_ARM_SYSROOT/usr/lib/python3/dist-packages/numpy/core/include"
  -DCMAKE_EXPORT_COMPILE_COMMANDS=ON)
for package in cv_bridge camera_models vins_estimator loop_fusion global_fusion; do
  source_dir="$repo/$package"
  if [[ "$package" = cv_bridge ]]; then
    source_dir="$repo/dependencies/sources/cv_bridge_ros2/3.2.1/cv_bridge"
  fi
  cmake -S "$source_dir" -B "$build/$package" "${common[@]}"
  cmake --build "$build/$package" -j "${VINS_BUILD_JOBS:-4}"
  cmake --install "$build/$package"
done
"$VINS_CROSS_ROOT/usr/bin/aarch64-linux-gnu-readelf" -h -d \
  "$VINS_ARM_ROS_PREFIX/lib/vins/vins_node" "$VINS_ARM_ROS_PREFIX/lib/vins/euroc_player_node"
printf 'ARM ROS 2 install built; board validation still required: %s\n' "$VINS_ARM_ROS_PREFIX"
