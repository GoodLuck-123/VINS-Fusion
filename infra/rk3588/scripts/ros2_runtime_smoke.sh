#!/usr/bin/env bash
set -euo pipefail
source "$VINS_REMOTE_PAYLOAD/runtime_env.sh"
python3 "$VINS_REMOTE_PAYLOAD/ros2_runtime_smoke.py"
