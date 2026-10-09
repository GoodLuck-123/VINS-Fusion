#!/usr/bin/env bash
# Source in a fresh terminal, independently of ros1_env.sh and the uv venv.
source "$(dirname "${BASH_SOURCE[0]}")/workspace_root.sh"
unset PYTHONPATH CMAKE_PREFIX_PATH AMENT_PREFIX_PATH COLCON_PREFIX_PATH LD_LIBRARY_PATH PKG_CONFIG_PATH VIRTUAL_ENV
unset ROS_MASTER_URI ROS_IP ROS_ROOT ROS_PACKAGE_PATH
eval "$("$VINS_WORKSPACE_DIR/.infra/bin/micromamba" shell hook -s bash -r "$VINS_WORKSPACE_DIR/.infra/mamba")"
micromamba activate "$VINS_WORKSPACE_DIR/.infra/ros2"
export ROS_HOME="$VINS_WORKSPACE_DIR/.infra/ros2-home"
export ROS_LOG_DIR="$ROS_HOME/log"
export XDG_CACHE_HOME="$VINS_WORKSPACE_DIR/.infra/cache"
export OpenCV_DIR="$VINS_WORKSPACE_DIR/.infra/legacy_ros2/lib/cmake/opencv4"
export Ceres_DIR="$VINS_WORKSPACE_DIR/.infra/legacy_ros2/lib/cmake/Ceres"
export CMAKE_PREFIX_PATH="$VINS_WORKSPACE_DIR/.infra/legacy_ros2:$CONDA_PREFIX"
export LD_LIBRARY_PATH="$VINS_WORKSPACE_DIR/.infra/legacy_ros2/lib:$CONDA_PREFIX/lib"
export PKG_CONFIG_PATH="$VINS_WORKSPACE_DIR/.infra/legacy_ros2/lib/pkgconfig:$CONDA_PREFIX/lib/pkgconfig"
export ROS_LOCALHOST_ONLY=1
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
if [[ -f "$VINS_WORKSPACE_DIR/.infra/ros2_ws/install/.vins-ready" && "${VINS_ROS2_BUILD:-0}" != 1 ]]; then
  source "$VINS_WORKSPACE_DIR/.infra/ros2_ws/install/setup.bash"
fi
