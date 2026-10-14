#!/usr/bin/env bash
# Source this deployed file on the board; do not source host SDK setup scripts.
vins_runtime_root=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
export VINS_ROS_PREFIX="$vins_runtime_root/.infra/ros2"
export VINS_BUILD_SOURCE_JSON="$vins_runtime_root/build_source.json"
export AMENT_PREFIX_PATH="$vins_runtime_root/.infra/ros2_ws/install:$VINS_ROS_PREFIX"
export LD_LIBRARY_PATH="$vins_runtime_root/.infra/ros2_ws/install/lib:$vins_runtime_root/.infra/runtime/lib:$VINS_ROS_PREFIX/lib"
export PYTHONPATH="$vins_runtime_root/.infra/ros2_ws/install/lib/python3.10/site-packages:$VINS_ROS_PREFIX/local/lib/python3.10/dist-packages:$VINS_ROS_PREFIX/lib/python3.10/site-packages:$vins_runtime_root/.infra/runtime/python"
export PATH="$VINS_ROS_PREFIX/bin:/usr/bin:/bin"
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-121}"
export ROS_LOCALHOST_ONLY=1
export CYCLONEDDS_URI="file://$vins_runtime_root/cyclonedds.xml"
unset vins_runtime_root
