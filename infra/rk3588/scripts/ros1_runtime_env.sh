#!/usr/bin/env bash
# Private Focal/Noetic Python 3.8; retain the board's glibc/loader and system Python.
vins_runtime_root=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
export VINS_ROS_PREFIX="$vins_runtime_root/.infra/ros1"
export VINS_BUILD_SOURCE_JSON="$vins_runtime_root/build_source.json"
export PYTHONHOME="$vins_runtime_root/.infra/python38"
export PYTHONPATH="$VINS_ROS_PREFIX/lib/python3/dist-packages:$vins_runtime_root/.infra/runtime/python"
export PYTHONNOUSERSITE=1
export LD_LIBRARY_PATH="$vins_runtime_root/.infra/vins_ws/devel/lib:$vins_runtime_root/.infra/runtime/lib:$VINS_ROS_PREFIX/lib"
export PATH="$PYTHONHOME/bin:$VINS_ROS_PREFIX/bin:/usr/bin:/bin"
export CMAKE_PREFIX_PATH="$vins_runtime_root/.infra/vins_ws/devel:$VINS_ROS_PREFIX"
export ROS_PACKAGE_PATH="$VINS_ROS_PREFIX/share"
export ROS_ROOT="$VINS_ROS_PREFIX/share/ros"
export ROS_ETC_DIR="$VINS_ROS_PREFIX/etc/ros"
export ROS_DISTRO=noetic ROS_VERSION=1 ROS_PYTHON_VERSION=3 ROS_IP=127.0.0.1
unset vins_runtime_root
