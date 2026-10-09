#!/usr/bin/env bash
# Source this in a fresh shell. Do not activate the uv environment in this shell.
source "$(dirname "${BASH_SOURCE[0]}")/workspace_root.sh"
VINS_ROOT="$VINS_WORKSPACE_DIR"
unset PYTHONPATH CMAKE_PREFIX_PATH LD_LIBRARY_PATH PKG_CONFIG_PATH VIRTUAL_ENV
eval "$("$VINS_ROOT/.infra/bin/micromamba" shell hook -s bash -r "$VINS_ROOT/.infra/mamba")"
micromamba activate "$VINS_ROOT/.infra/ros1"
export ROS_HOME="$VINS_ROOT/.infra/ros-home"
export ROS_LOG_DIR="$ROS_HOME/log"
export XDG_CACHE_HOME="$VINS_ROOT/.infra/cache"
export PIP_CACHE_DIR="$VINS_ROOT/.infra/pip-cache"
export ROS_IP=127.0.0.1
export ROS_MASTER_URI=http://127.0.0.1:11311
export CMAKE_PREFIX_PATH="$VINS_ROOT/.infra/legacy:$CONDA_PREFIX${CMAKE_PREFIX_PATH:+:$CMAKE_PREFIX_PATH}"
export LD_LIBRARY_PATH="$VINS_ROOT/.infra/legacy/lib:$CONDA_PREFIX/lib"
export PKG_CONFIG_PATH="$VINS_ROOT/.infra/legacy/lib/pkgconfig:$CONDA_PREFIX/lib/pkgconfig"
export OpenCV_DIR="$VINS_ROOT/.infra/legacy/lib/cmake/opencv4"
export Ceres_DIR="$VINS_ROOT/.infra/legacy/lib/cmake/Ceres"
if [[ -f "$VINS_ROOT/.infra/bridge_ws/devel/setup.bash" ]]; then
  source "$VINS_ROOT/.infra/bridge_ws/devel/setup.bash"
fi
if [[ -f "$VINS_ROOT/.infra/vins_ws/devel/setup.bash" ]]; then
  source "$VINS_ROOT/.infra/vins_ws/devel/setup.bash"
fi
