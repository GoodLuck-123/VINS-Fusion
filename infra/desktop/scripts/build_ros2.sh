#!/usr/bin/env bash
set -eo pipefail
export VINS_ROS2_BUILD=1
source "$(dirname "${BASH_SOURCE[0]}")/ros2_env.sh"
set -u
export MAKEFLAGS="-j${VINS_BUILD_JOBS:-4}"
export CMAKE_BUILD_PARALLEL_LEVEL="${VINS_BUILD_JOBS:-4}"
VINS_ROS2_WS="$VINS_WORKSPACE_DIR/.infra/ros2_ws"
mkdir -p "$VINS_ROS2_WS"
cd "$VINS_ROS2_WS"
colcon build --merge-install --executor sequential \
  --base-paths "$VINS_WORKSPACE_DIR/.infra/src/vision_opencv-3.2.1/cv_bridge" \
    "$VINS_REPO_DIR/camera_models" "$VINS_REPO_DIR/vins_estimator" \
    "$VINS_REPO_DIR/loop_fusion" "$VINS_REPO_DIR/global_fusion" \
  --cmake-args -G Ninja -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF \
    -DOpenCV_DIR="$OpenCV_DIR" -DCeres_DIR="$Ceres_DIR" \
    -DEigen3_DIR="$CONDA_PREFIX/share/eigen3/cmake" \
    -DPython3_EXECUTABLE="$CONDA_PREFIX/bin/python" \
    -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
    -DCMAKE_INSTALL_LIBDIR=lib \
  --parallel-workers "${VINS_BUILD_JOBS:-4}"
touch "$VINS_ROS2_WS/install/.vins-ready"
