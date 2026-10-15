#!/usr/bin/env bash
set -euo pipefail
export VINS_RMW=rmw_fastrtps_cpp
"$HOME/vins-workspace/releases/ros2-v0.1/install/bin/vins" check "$VINS_REMOTE_ROOT/logs/runtime-check"
